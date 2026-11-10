package com.example.util

import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileOutputStream

object ShareHelper {

    fun shareCliReceiver(context: Context) {
        try {
            val cacheFile = File(context.cacheDir, "phonemic_cli.py")
            context.assets.open("phonemic_cli.py").use { input ->
                FileOutputStream(cacheFile).use { output ->
                    input.copyTo(output)
                }
            }

            val uri = FileProvider.getUriForFile(
                context,
                "${context.packageName}.fileprovider",
                cacheFile
            )

            val shareIntent = Intent(Intent.ACTION_SEND).apply {
                type = "text/x-python"
                putExtra(Intent.EXTRA_STREAM, uri)
                putExtra(
                    Intent.EXTRA_SUBJECT,
                    "PhoneMic Standalone CLI Receiver"
                )
                putExtra(
                    Intent.EXTRA_TEXT,
                    "PhoneMic Standalone CLI Receiver v${com.example.BuildConfig.VERSION_NAME}\n\n" +
                    "Run with:\n" +
                    "  pip install numpy sounddevice\n" +
                    "  python phonemic_cli.py\n\n" +
                    "Supports multi-device mixing, real-time headphone monitoring ('M' key), and low-bandwidth profiles."
                )
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }

            val chooser = Intent.createChooser(shareIntent, "Share PhoneMic Receiver to PC / Device")
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(chooser)
        } catch (e: Exception) {
            Toast.makeText(context, "Error sharing receiver: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }
}
