package au.dropline.routeplanner;

import android.Manifest;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.ActivityNotFoundException;
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
        permissions = {
            @Permission(strings = { Manifest.permission.POST_NOTIFICATIONS }, alias = "notifications"),
            @Permission(strings = { Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION }, alias = "location")
        })
public class DevicePlugin extends Plugin {
    private static final String CHANNEL = "dropline";
    private static java.lang.ref.WeakReference<DevicePlugin> current = new java.lang.ref.WeakReference<>(null);

    /** Phone Back button: the app closes its own screens first (sheets, Settings pages, navigation). Returns false when the app has nothing to close. */
    static boolean sendBack() {
        DevicePlugin p = current.get();
        if (p != null && p.hasListeners("back")) { p.notifyListeners("back", new JSObject()); return true; }
        return false;
    }

    @Override
    public void load() {
        current = new java.lang.ref.WeakReference<>(this);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "Dropline", NotificationManager.IMPORTANCE_DEFAULT);
            ch.setDescription("Route ready, downloads finished, run finished");
            ch.setShowBadge(false);                      // no number on the app icon
            getContext().getSystemService(NotificationManager.class).createNotificationChannel(ch);
        }
    }

    /** "granted", "denied" (blocked: only the phone's Settings can change it) or "prompt" (not asked yet: the app can ask). */
    private static String word(PermissionState s) {
        if (s == PermissionState.GRANTED) return "granted";
        if (s == PermissionState.DENIED) return "denied";
        return "prompt";
    }
    private String locationState() {
        Context c = getContext();
        boolean fine = ContextCompat.checkSelfPermission(c, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        boolean coarse = ContextCompat.checkSelfPermission(c, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        if (fine || coarse) return "granted";
        try { return word(getPermissionState("location")); } catch (Exception e) { return "prompt"; }
    }
    private String notificationState() {
        if (NotificationManagerCompat.from(getContext()).areNotificationsEnabled()) return "granted";
        if (Build.VERSION.SDK_INT >= 33) {
            try {
                PermissionState s = getPermissionState("notifications");
                if (s != PermissionState.GRANTED) return word(s);      // not asked yet → the app can ask
            } catch (Exception e) { return "prompt"; }
        }
        return "denied";                                              // turned off in the phone's Settings
    }

    /** Ask for location with the phone's own prompt (one prompt; the website never asks separately). */
    @PluginMethod
    public void requestLocation(PluginCall call) {
        if ("granted".equals(locationState())) { JSObject r = new JSObject(); r.put("location", "granted"); call.resolve(r); return; }
        requestPermissionForAlias("location", call, "locCallback");
    }
    @PermissionCallback
    private void locCallback(PluginCall call) {
        JSObject r = new JSObject(); r.put("location", locationState()); call.resolve(r);
    }

    /** Back on the first screen: leave the app (it stays ready in the background, like other apps). */
    @PluginMethod
    public void exitApp(PluginCall call) {
        call.resolve();
        getActivity().runOnUiThread(() -> getActivity().moveTaskToBack(true));
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

    /** Chat with the developer: WhatsApp when it is installed, otherwise the phone's messaging app. */
    @PluginMethod
    public void openChat(PluginCall call) {
        String phone = call.getString("phone", ""), text = call.getString("text", "");
        Context c = getContext(); PackageManager pm = c.getPackageManager(); String pkg = null;
        for (String p : new String[] { "com.whatsapp", "com.whatsapp.w4b" }) {
            try { pm.getPackageInfo(p, 0); pkg = p; break; } catch (Exception e) { /* not installed */ }
        }
        Intent i;
        if (pkg != null) {
            i = new Intent(Intent.ACTION_VIEW, Uri.parse("https://api.whatsapp.com/send?phone=" + phone + "&text=" + Uri.encode(text)));
            i.setPackage(pkg);
        } else {
            i = new Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:+" + phone));
            i.putExtra("sms_body", text);
        }
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            c.startActivity(i);
            JSObject r = new JSObject(); r.put("app", pkg != null ? "whatsapp" : "sms"); call.resolve(r);
        } catch (ActivityNotFoundException e) { call.reject("No chat app found"); }
    }

    /** Share a small text file (a route) through the Android share sheet: Drive, WhatsApp, Gmail… */
    @PluginMethod
    public void shareFile(PluginCall call) {
        try {
            Context c = getContext();
            String name = call.getString("name", "dropline-route.json").replace("/", "-");
            java.io.File dir = new java.io.File(c.getCacheDir(), "shared"); dir.mkdirs();
            java.io.File f = new java.io.File(dir, name);
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(f)) { out.write(call.getString("text", "").getBytes(java.nio.charset.StandardCharsets.UTF_8)); }
            Uri uri = androidx.core.content.FileProvider.getUriForFile(c, c.getPackageName() + ".fileprovider", f);
            Intent send = new Intent(Intent.ACTION_SEND).setType("application/json").putExtra(Intent.EXTRA_STREAM, uri)
                    .putExtra(Intent.EXTRA_SUBJECT, call.getString("title", "DropLine route")).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            Intent chooser = Intent.createChooser(send, call.getString("title", "Share route")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            c.startActivity(chooser);
            JSObject r = new JSObject(); r.put("shared", true); call.resolve(r);
        } catch (Exception e) { call.reject("Could not share the file"); }
    }

    @PluginMethod
    public void clearBadge(PluginCall call) {
        NotificationManagerCompat.from(getContext()).cancelAll();   // launchers show a number only while notifications are waiting
        call.resolve();
    }
}
