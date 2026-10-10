package com.example

import android.content.Context
import android.net.ConnectivityManager
import android.net.LinkAddress
import android.net.Network
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import java.io.IOException
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.SocketException
import java.net.SocketTimeoutException
import java.nio.charset.StandardCharsets
import java.util.Collections

/**
 * Finds the PC running the receiver so the IP address does not have to be manually typed.
 * Sends discovery query "PMD0" and listens for "PMA1" reply from receiver.
 * Fully compatible with Android 7.1.1 (API 25) and Android 10 (API 29).
 */
object ReceiverDiscovery {

    private const val TAG = "PhoneMic-Discovery"
    private const val QUERY = "PMD0"
    private const val REPLY = "PMA1"
    private const val QUERY_INTERVAL_MS = 250
    private const val PACKET_BUFFER = 64

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
        val targets = broadcastTiers(context, preferUsb)
        val mainHandler = Handler(Looper.getMainLooper())

        val worker = Thread({
            // Acquire MulticastLock: Critical for Android 7.1.1 & 10 to receive broadcast UDP replies
            val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            val multicastLock = wm?.createMulticastLock("PhoneMic:Discovery")
            multicastLock?.setReferenceCounted(false)
            try {
                multicastLock?.acquire()
            } catch (_: Exception) {}

            try {
                val result = search(targets, port)
                mainHandler.post {
                    if (result.ip != null) {
                        callback.onFound(result.ip)
                    } else {
                        callback.onFailed(result.reason ?: "No PC receiver answered")
                    }
                }
            } finally {
                try {
                    multicastLock?.release()
                } catch (_: Exception) {}
            }
        }, "PhoneMic-Discovery")
        worker.isDaemon = true
        worker.start()
    }

    private data class Result(val ip: String?, val reason: String?)

    private fun search(tiers: List<List<String>>, port: Int): Result {
        if (tiers.isEmpty()) {
            return Result(null, "No network interface available")
        }

        var socket: DatagramSocket? = null
        try {
            socket = DatagramSocket()
            socket.broadcast = true

            val query = QUERY.toByteArray(StandardCharsets.US_ASCII)
            val buffer = ByteArray(PACKET_BUFFER)

            for (t in tiers.indices) {
                val tier = tiers[t]
                if (tier.isEmpty()) continue

                Log.i(TAG, "Tier $t searching: $tier on port $port")
                val tierDeadline = SystemClock.elapsedRealtime() + tierTimeoutMillis(t)

                while (SystemClock.elapsedRealtime() < tierDeadline) {
                    for (target in tier) {
                        try {
                            socket.send(
                                DatagramPacket(
                                    query,
                                    query.size,
                                    InetSocketAddress(target, port)
                                )
                            )
                        } catch (_: Exception) {
                            // Target might be unreachable, try next in tier
                        }
                    }

                    val remaining = tierDeadline - SystemClock.elapsedRealtime()
                    val wait = Math.min(QUERY_INTERVAL_MS.toLong(), Math.max(1L, remaining)).toInt()

                    socket.soTimeout = wait
                    try {
                        val response = DatagramPacket(buffer, buffer.size)
                        socket.receive(response)

                        val payload = String(
                            response.data,
                            0,
                            response.length,
                            StandardCharsets.US_ASCII
                        ).trim()

                        Log.i(TAG, "Received response from ${response.socketAddress}: '$payload'")

                        if (payload.contains(REPLY) || payload.startsWith("PMA")) {
                            val from = response.address
                            if (from is Inet4Address) {
                                val host = from.hostAddress
                                Log.i(TAG, "Found receiver at $host")
                                return Result(host, null)
                            }
                        }
                    } catch (_: SocketTimeoutException) {
                        // Expected: continue querying
                    }
                }
            }

            return Result(null, "No PC answered. Ensure python script is running and Windows Firewall allows port $port.")
        } catch (e: Exception) {
            Log.e(TAG, "Discovery error", e)
            return Result(null, e.message ?: "Search failed")
        } finally {
            socket?.close()
        }
    }

    private fun broadcastTiers(context: Context, preferUsb: Boolean): List<List<String>> {
        val preferred = LinkedHashSet<String>()
        val secondary = LinkedHashSet<String>()
        val others = LinkedHashSet<String>()

        // 1. Direct gateway and common tethering host IPs (Unicast - never blocked by router broadcast filters)
        val knownHosts = listOf(
            "192.168.137.1", // Windows Mobile Hotspot default host IP
            "192.168.42.1",   // Common USB tether host IP
            "192.168.42.2",
            "192.168.43.1",   // Common Android hotspot host IP
            "192.168.1.1",
            "192.168.0.1"
        )
        if (preferUsb) {
            preferred.addAll(knownHosts)
        } else {
            secondary.addAll(knownHosts)
        }

        // 2. Hardware network interfaces (rndis for USB on Android 7.1.1, wlan for Wi-Fi)
        for (candidate in usableInterfaces()) {
            val broadcast = broadcastFor(candidate.address, candidate.prefixLength)
            if (broadcast != null) {
                when (classify(candidate.name)) {
                    KIND_TETHER -> (if (preferUsb) preferred else secondary).add(broadcast)
                    KIND_WIFI -> (if (preferUsb) secondary else preferred).add(broadcast)
                    else -> others.add(broadcast)
                }
            }
        }

        // 3. ConnectivityManager networks
        val cm = connectivityManager(context)
        if (cm != null) {
            for (network in reportedNetworks(cm)) {
                val tether = hasTetherTransport(cm, network)
                val targetSet = if (tether) {
                    if (preferUsb) preferred else secondary
                } else {
                    if (preferUsb) secondary else preferred
                }
                targetSet.addAll(networkBroadcasts(cm, network))
            }
        }

        return listOf(
            preferred.toList(),
            secondary.toList(),
            others.toList(),
            listOf("255.255.255.255")
        )
    }

    private fun tierTimeoutMillis(tierIndex: Int): Long {
        return when (tierIndex) {
            0 -> 1500L
            1 -> 1200L
            else -> 800L
        }
    }

    private const val KIND_TETHER = 0
    private const val KIND_WIFI = 1
    private const val KIND_OTHER = 2

    private fun classify(name: String?): Int {
        if (name == null) return KIND_OTHER
        val lower = name.lowercase()
        return when {
            lower.startsWith("rndis") || lower.startsWith("usb") || lower.startsWith("eth") -> KIND_TETHER
            lower.startsWith("wlan") -> KIND_WIFI
            else -> KIND_OTHER
        }
    }

    private data class InterfaceCandidate(
        val name: String,
        val address: InetAddress,
        val prefixLength: Int
    )

    private fun usableInterfaces(): List<InterfaceCandidate> {
        val result = mutableListOf<InterfaceCandidate>()
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces() ?: return result
            for (nic in Collections.list(interfaces)) {
                if (nic.isLoopback || !nic.isUp) continue
                val name = nic.name
                for (info in nic.interfaceAddresses) {
                    val addr = info.address
                    if (addr is Inet4Address) {
                        result.add(
                            InterfaceCandidate(
                                name = name,
                                address = addr,
                                prefixLength = info.networkPrefixLength.toInt()
                            )
                        )
                    }
                }
            }
        } catch (_: SocketException) {
        }
        return result
    }

    private fun hasTetherTransport(cm: ConnectivityManager, network: Network): Boolean {
        return try {
            val caps = cm.getNetworkCapabilities(network)
            caps != null && (
                caps.hasTransport(NetworkCapabilities.TRANSPORT_USB) ||
                caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
            )
        } catch (_: Exception) {
            false
        }
    }

    private fun connectivityManager(context: Context): ConnectivityManager? {
        return try {
            context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        } catch (_: Exception) {
            null
        }
    }

    private fun reportedNetworks(cm: ConnectivityManager): List<Network> {
        val result = mutableListOf<Network>()
        try {
            for (network in cm.allNetworks) {
                val caps = cm.getNetworkCapabilities(network) ?: continue
                if (caps.hasTransport(NetworkCapabilities.TRANSPORT_USB) ||
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) ||
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                ) {
                    result.add(network)
                }
            }
        } catch (_: Exception) {
        }
        return result
    }

    private fun networkBroadcasts(cm: ConnectivityManager, network: Network): List<String> {
        val result = mutableListOf<String>()
        try {
            val properties = cm.getLinkProperties(network) ?: return result
            for (link in properties.linkAddresses) {
                val b = broadcastFor(link.address, link.prefixLength)
                if (b != null) result.add(b)
            }
        } catch (_: Exception) {
        }
        return result
    }

    private fun broadcastFor(address: InetAddress, prefixLength: Int): String? {
        if (address !is Inet4Address || prefixLength !in 0..32) {
            return null
        }
        val octets = address.address ?: return null
        if (octets.size != 4) return null

        var value = 0
        for (i in 0..3) {
            value = (value shl 8) or (octets[i].toInt() and 0xFF)
        }

        val networkMask = if (prefixLength == 0) 0 else ((1.toLong() shl (32 - prefixLength)) - 1).inv().toInt()
        val broadcastValue = (value and networkMask) or networkMask.inv()

        val broadcast = byteArrayOf(
            (broadcastValue ushr 24).toByte(),
            (broadcastValue ushr 16).toByte(),
            (broadcastValue ushr 8).toByte(),
            broadcastValue.toByte()
        )

        return try {
            InetAddress.getByAddress(broadcast).hostAddress
        } catch (_: Exception) {
            null
        }
    }
}
