package com.srmp.srmp_monitor

import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.SharedPreferences
import android.widget.RemoteViews
import es.antonborri.home_widget.HomeWidgetProvider

class AppWidgetProvider : HomeWidgetProvider() {
    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray, widgetData: SharedPreferences) {
        appWidgetIds.forEach { widgetId ->
            val views = RemoteViews(context.packageName, R.layout.widget_layout).apply {
                val cpu = widgetData.getString("cpu", "--%")
                val ram = widgetData.getString("ram", "--%")
                val disk = widgetData.getString("disk", "--%")
                val status = widgetData.getString("status", "Offline")

                setTextViewText(R.id.tv_cpu, cpu)
                setTextViewText(R.id.tv_ram, ram)
                setTextViewText(R.id.tv_disk, disk)
                setTextViewText(R.id.tv_status, status)
            }
            appWidgetManager.updateAppWidget(widgetId, views)
        }
    }
}
