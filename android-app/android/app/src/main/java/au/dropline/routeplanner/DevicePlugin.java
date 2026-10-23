package au.dropline.routeplanner;

import android.Manifest;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;

import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

/** Small phone helpers for Dropline: permission status, open the app's Settings page, local notifications, clear the icon badge. */
@CapacitorPlugin(name = "DroplineDevice",
        permissions = { @Permission(strings = { Manifest.permission.POST_NOTIFICATIONS }, alias = "notifications") })
public class DevicePlugin extends Plugin {
    private static final String CHANNEL = "dropline";

    @Override
    public void load() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "Dropline", NotificationManager.IMPORTANCE_DEFAULT);
            ch.setDescription("Route ready, downloads finished, run finished");
            ch.setShowBadge(false);                      // no number on the app icon
            getContext().getSystemService(NotificationManager.class).createNotificationChannel(ch);
        }
    }

    private String locationState() {
        Context c = getContext();
        boolean fine = ContextCompat.checkSelfPermission(c, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        boolean coarse = ContextCompat.checkSelfPermission(c, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        return (fine || coarse) ? "granted" : "denied";
    }
    private String notificationState() {
        return NotificationManagerCompat.from(getContext()).areNotificationsEnabled() ? "granted" : "denied";
    }

    @PluginMethod
    public void permissions(PluginCall call) {
        JSObject r = new JSObject();
        r.put("location", locationState());
        r.put("notifications", notificationState());
        r.put("platform", "android");
        call.resolve(r);
    }

    @PluginMethod
    public void requestNotifications(PluginCall call) {
        if (Build.VERSION.SDK_INT >= 33 && getPermissionState("notifications") != PermissionState.GRANTED) {
            requestPermissionForAlias("notifications", call, "notifCallback");
        } else {
            JSObject r = new JSObject(); r.put("notifications", notificationState()); call.resolve(r);
        }
    }
    @PermissionCallback
    private void notifCallback(PluginCall call) {
        JSObject r = new JSObject(); r.put("notifications", notificationState()); call.resolve(r);
    }

    @PluginMethod
    public void openSettings(PluginCall call) {
        Context c = getContext();
        Intent i;
        if ("notifications".equals(call.getString("target")) && Build.VERSION.SDK_INT >= 26) {
            i = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, c.getPackageName());
        } else {
            i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", c.getPackageName(), null));
        }
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try { c.startActivity(i); call.resolve(); } catch (Exception e) { call.reject("Could not open Settings"); }
    }

    @PluginMethod
    public void notify(PluginCall call) {
        Context c = getContext();
        if (!NotificationManagerCompat.from(c).areNotificationsEnabled()) { call.reject("Notifications are off"); return; }
        Intent open = new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(c, 0, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        NotificationCompat.Builder b = new NotificationCompat.Builder(c, CHANNEL)
                .setSmallIcon(R.drawable.ic_stat_dropline)
                .setContentTitle(call.getString("title", "Dropline"))
                .setContentText(call.getString("body", ""))
                .setStyle(new NotificationCompat.BigTextStyle().bigText(call.getString("body", "")))
                .setContentIntent(pi).setAutoCancel(true)
                .setBadgeIconType(NotificationCompat.BADGE_ICON_NONE).setNumber(0)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT);
        try {
            NotificationManagerCompat.from(c).notify(call.getInt("id", 1), b.build());
            call.resolve();
        } catch (SecurityException e) { call.reject("Notifications are off"); }
    }

    @PluginMethod
    public void clearBadge(PluginCall call) {
        NotificationManagerCompat.from(getContext()).cancelAll();   // launchers show a number only while notifications are waiting
        call.resolve();
    }
}
