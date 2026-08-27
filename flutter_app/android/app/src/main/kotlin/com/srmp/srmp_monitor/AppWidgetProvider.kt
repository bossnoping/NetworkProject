package com.srmp.srmp_monitor

import android.appwidget.AppWidgetManager
import android.app.PendingIntent
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.widget.RemoteViews
import es.antonborri.home_widget.HomeWidgetProvider
import java.net.Socket

class AppWidgetProvider : HomeWidgetProvider() {
    companion object {
        private const val ACTION_LOCK = "com.srmp.srmp_monitor.LOCK"
        private const val ACTION_RESTART = "com.srmp.srmp_monitor.RESTART"
        private const val ACTION_SHUTDOWN = "com.srmp.srmp_monitor.SHUTDOWN"
        private const val ACTION_VOLUME_UP = "com.srmp.srmp_monitor.VOLUME_UP"
        private const val ACTION_BRIGHTNESS_UP = "com.srmp.srmp_monitor.BRIGHTNESS_UP"
        private const val PREFS = "HomeWidgetPreferences"
    }

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray, widgetData: SharedPreferences) {
        appWidgetIds.forEach { widgetId ->
            val views = RemoteViews(context.packageName, R.layout.widget_layout).apply {
                val cpu = widgetData.getString("cpu", "--%")
                val ram = widgetData.getString("ram", "--%")
                val disk = widgetData.getString("disk", "--%")
                val temp = widgetData.getString("temp", "--°C")
                val status = widgetData.getString("status", "OFFLINE")
                val result = widgetData.getString("widget_result", "Ready")

                setTextViewText(R.id.tv_cpu, cpu)
                setTextViewText(R.id.tv_ram, ram)
                setTextViewText(R.id.tv_disk, disk)
                setTextViewText(R.id.tv_temp, temp)
                setTextViewText(R.id.tv_status, status)
                setTextViewText(R.id.tv_result, result)
                setOnClickPendingIntent(R.id.btn_lock, actionIntent(context, ACTION_LOCK))
                setOnClickPendingIntent(R.id.btn_restart, actionIntent(context, ACTION_RESTART))
                setOnClickPendingIntent(R.id.btn_shutdown, actionIntent(context, ACTION_SHUTDOWN))
                setOnClickPendingIntent(R.id.btn_volume, actionIntent(context, ACTION_VOLUME_UP))
                setOnClickPendingIntent(R.id.btn_brightness, actionIntent(context, ACTION_BRIGHTNESS_UP))
            }
            appWidgetManager.updateAppWidget(widgetId, views)
        }
    }

    private fun actionIntent(context: Context, action: String): PendingIntent {
        val intent = Intent(context, AppWidgetProvider::class.java).setAction(action)
        return PendingIntent.getBroadcast(
            context,
            action.hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action !in setOf(ACTION_LOCK, ACTION_RESTART, ACTION_SHUTDOWN, ACTION_VOLUME_UP, ACTION_BRIGHTNESS_UP)) return

        val pendingResult = goAsync()
        Thread {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val host = prefs.getString("server_host", null)
            val command = when (intent.action) {
                ACTION_LOCK -> "SYS_POWER action=LOCK"
                ACTION_RESTART -> "SYS_POWER action=RESTART"
                ACTION_SHUTDOWN -> "SYS_POWER action=SHUTDOWN"
                ACTION_VOLUME_UP -> "SET_VOL level=${(prefs.getString("volume", "50")?.toIntOrNull() ?: 50).coerceAtMost(100) + 10}"
                else -> "SET_BRIGHTNESS level=${(prefs.getString("brightness", "50")?.toIntOrNull() ?: 50).coerceAtMost(100) + 10}"
            }
            val result = if (host == null) {
                "Connect in app first"
            } else {
                try {
                    Socket(host, 9001).use { socket ->
                        socket.getOutputStream().write("$command\n".toByteArray())
                        socket.getInputStream().bufferedReader().readLine() ?: "No response"
                    }
                } catch (error: Exception) {
                    "Offline: ${error.message ?: "connection failed"}"
                }
            }
            prefs.edit().putString("widget_result", result).apply()
            AppWidgetManager.getInstance(context).updateAppWidget(
                ComponentName(context, AppWidgetProvider::class.java),
                RemoteViews(context.packageName, R.layout.widget_layout).apply {
                    setTextViewText(R.id.tv_result, result)
                },
            )
            pendingResult.finish()
        }.start()
    }
}
