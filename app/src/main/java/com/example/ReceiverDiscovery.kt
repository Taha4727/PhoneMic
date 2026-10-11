package com.example

import android.content.Context
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.SocketTimeoutException
import java.nio.charset.StandardCharsets
import java.util.Collections
import java.util.concurrent.atomic.AtomicBoolean

/**
 * High-speed PC receiver auto-discovery engine.
 * Supports Android 7.1.1 (Samsung Galaxy J5), Android 11 (Samsung A10s), and Android 16 (POCO X6 Pro).
 *
 * Employs a hybrid discovery model:
 * 1. Broadcast queries (255.255.255.255 & subnet broadcast)
 * 2. Unicast sweep across local /24 subnet (bypasses Wi-Fi router AP/broadcast isolation)
 * 3. Direct tethering host IPs (USB RNDIS 192.168.42.x, Windows Hotspot 192.168.137.1)
 */
object ReceiverDiscovery {

    private const val TAG = "PhoneMic-Discovery"
    private const val QUERY = "PMD0"
    private const val REPLY_PREFIX = "PMA"
    private const val PACKET_BUFFER = 128

    interface Callback {
        fun onFound(ip: String)
        fun onFailed(reason: String)
    }

    fun find(
        context: Context,
        port: Int,
        preferUsb: Boolean,
        callback: Callback
    ) {
        val mainHandler = Handler(Looper.getMainLooper())

        val worker = Thread({
            // Acquire MulticastLock: Critical for Android 7.1.1, 11, & 16 to receive UDP discovery packets
            val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            val multicastLock = wm?.createMulticastLock("PhoneMic:Discovery")
            multicastLock?.setReferenceCounted(false)
            try {
                multicastLock?.acquire()
            } catch (_: Exception) {}

            try {
                val foundIp = executeDiscovery(port, preferUsb)
                mainHandler.post {
                    if (foundIp != null) {
                        callback.onFound(foundIp)
                    } else {
                        callback.onFailed("No PC receiver found. Ensure receiver is running on PC (Port $port)")
                    }
                }
            } finally {
                try {
                    multicastLock?.release()
                } catch (_: Exception) {}
            }
        }, "PhoneMic-DiscoveryWorker")

        worker.isDaemon = true
        worker.start()
    }

    private fun executeDiscovery(port: Int, preferUsb: Boolean): String? {
        var socket: DatagramSocket? = null
        val found = AtomicBoolean(false)
        var discoveredIp: String? = null

        try {
            socket = DatagramSocket()
            socket.broadcast = true
            socket.soTimeout = 350

            val query = QUERY.toByteArray(StandardCharsets.US_ASCII)
            val buffer = ByteArray(PACKET_BUFFER)

            // Gather local subnets and interfaces
            val localNics = getActiveSubnets()
            val targetIps = LinkedHashSet<String>()

            // 1. Direct gateway & USB tethering host addresses
            // Note: On Windows RNDIS tethering, the PC is typically assigned 192.168.42.129, 192.168.42.1, or 192.168.42.2
            val usbTetherHosts = listOf(
                "192.168.42.129", // Standard Windows RNDIS host IP
                "192.168.42.1",   // Alternative tether gateway
                "192.168.42.2",   // Secondary tether IP
                "192.168.42.3",
                "192.168.42.255", // USB subnet broadcast
                "192.168.137.1",  // Windows Mobile Hotspot default host IP
                "192.168.137.255"
            )

            val wifiCommonHosts = listOf(
                "192.168.1.1",
                "192.168.0.1",
                "192.168.43.1"
            )

            if (preferUsb) {
                targetIps.addAll(usbTetherHosts)
            } else {
                targetIps.addAll(wifiCommonHosts)
            }

            // 2. Add broadcast targets
            targetIps.add("255.255.255.255")
            for (nic in localNics) {
                if (nic.broadcast != null) {
                    targetIps.add(nic.broadcast)
                }
            }

            if (!preferUsb) {
                targetIps.addAll(usbTetherHosts)
            }

            // Dedicated Listener Thread
            val listenerThread = Thread({
                val responsePacket = DatagramPacket(buffer, buffer.size)
                while (!found.get() && !Thread.currentThread().isInterrupted) {
                    try {
                        socket.receive(responsePacket)
                        val text = String(
                            responsePacket.data,
                            0,
                            responsePacket.length,
                            StandardCharsets.US_ASCII
                        ).trim()

                        Log.i(TAG, "Discovery reply from ${responsePacket.address}: '$text' (preferUsb=$preferUsb)")

                        if (text.startsWith(REPLY_PREFIX)) {
                            val sender = responsePacket.address
                            if (sender is Inet4Address) {
                                val host = sender.hostAddress ?: ""
                                // Extract embedded IP in reply if provided: "PMA1 0.6.5 192.168.42.129"
                                val parts = text.split(" ")
                                val embeddedIp = if (parts.size >= 3 && parts[2].matches(Regex("^(\\d{1,3}\\.){3}\\d{1,3}$"))) {
                                    parts[2]
                                } else {
                                    null
                                }

                                val chosenIp: String = if (preferUsb) {
                                    // In USB mode: Prioritize the USB network interface (192.168.42.x or 192.168.137.x).
                                    // Never allow a Wi-Fi IP (e.g. 192.168.1.x) to hijack USB mode.
                                    if (host.startsWith("192.168.42.") || host.startsWith("192.168.137.")) {
                                        host
                                    } else if (embeddedIp != null && (embeddedIp.startsWith("192.168.42.") || embeddedIp.startsWith("192.168.137."))) {
                                        embeddedIp
                                    } else {
                                        // If reply arrived over USB link but host reports something else, socket sender address is real
                                        host.ifEmpty { embeddedIp ?: "" }
                                    }
                                } else {
                                    // In Wi-Fi mode: Prefer embedded IP or sender IP, avoiding USB tether subnets
                                    if (embeddedIp != null && !embeddedIp.startsWith("192.168.42.")) {
                                        embeddedIp
                                    } else if (!host.startsWith("192.168.42.")) {
                                        host
                                    } else {
                                        embeddedIp ?: host
                                    }
                                }

                                if (chosenIp.isNotBlank()) {
                                    discoveredIp = chosenIp
                                    found.set(true)
                                    break
                                }
                            }
                        }
                    } catch (_: SocketTimeoutException) {
                        // Continue listening
                    } catch (_: Exception) {
                        break
                    }
                }
            }, "PhoneMic-DiscoveryListener")
            listenerThread.isDaemon = true
            listenerThread.start()

            val deadline = SystemClock.elapsedRealtime() + 3500L

            // Stage 1: Send to primary targets and broadcasts
            for (ip in targetIps) {
                if (found.get()) break
                sendQuery(socket, query, ip, port)
            }

            // Stage 2: Sweep USB subnet (192.168.42.x) if in USB mode to guarantee hit on Samsung/Xiaomi
            if (preferUsb) {
                for (hostNum in 1..254) {
                    if (found.get()) break
                    sendQuery(socket, query, "192.168.42.$hostNum", port)
                    if (hostNum % 32 == 0) {
                        Thread.sleep(3)
                    }
                }
            }

            // Stage 3: Fast Unicast Subnet Sweep across local /24 subnets
            for (nic in localNics) {
                if (found.get()) break
                val base = nic.subnetPrefix ?: continue
                val myHostNum = nic.myHostNum

                // If in USB mode, skip sweeping standard Wi-Fi if already checked
                if (preferUsb && (base.startsWith("192.168.1") || base.startsWith("192.168.0"))) {
                    continue
                }

                // Sweep 1..254 (skip phone's own IP)
                for (hostNum in 1..254) {
                    if (found.get()) break
                    if (hostNum == myHostNum) continue
                    val target = "$base.$hostNum"
                    sendQuery(socket, query, target, port)

                    // Small yield every 32 packets to prevent socket buffer congestion
                    if (hostNum % 32 == 0) {
                        Thread.sleep(3)
                    }
                }
            }

            // Stage 4: Wait for listener to receive response or timeout
            while (!found.get() && SystemClock.elapsedRealtime() < deadline) {
                // Re-send to primary targets periodically
                for (ip in targetIps) {
                    if (found.get()) break
                    sendQuery(socket, query, ip, port)
                }
                Thread.sleep(200)
            }

            listenerThread.interrupt()
            return discoveredIp

        } catch (e: Exception) {
            Log.e(TAG, "Discovery error", e)
            return null
        } finally {
            try {
                socket?.close()
            } catch (_: Exception) {}
        }
    }

    private fun sendQuery(socket: DatagramSocket, query: ByteArray, target: String, port: Int) {
        try {
            val addr = InetSocketAddress(target, port)
            socket.send(DatagramPacket(query, query.size, addr))
        } catch (_: Exception) {
            // Target might be unreachable or interface temporarily down
        }
    }

    private data class NicInfo(
        val ip: String,
        val subnetPrefix: String?,
        val myHostNum: Int,
        val broadcast: String?
    )

    private fun getActiveSubnets(): List<NicInfo> {
        val list = mutableListOf<NicInfo>()
        try {
            val nics = NetworkInterface.getNetworkInterfaces() ?: return list
            for (nic in Collections.list(nics)) {
                if (nic.isLoopback || !nic.isUp) continue
                for (info in nic.interfaceAddresses) {
                    val addr = info.address
                    if (addr is Inet4Address && !addr.isLoopbackAddress) {
                        val hostIp = addr.hostAddress ?: continue
                        val parts = hostIp.split(".")
                        if (parts.size == 4) {
                            val prefix = "${parts[0]}.${parts[1]}.${parts[2]}"
                            val hostNum = parts[3].toIntOrNull() ?: -1
                            val broadcast = info.broadcast?.hostAddress ?: "$prefix.255"
                            list.add(
                                NicInfo(
                                    ip = hostIp,
                                    subnetPrefix = prefix,
                                    myHostNum = hostNum,
                                    broadcast = broadcast
                                )
                            )
                        }
                    }
                }
            }
        } catch (_: Exception) {}
        return list
    }
}
