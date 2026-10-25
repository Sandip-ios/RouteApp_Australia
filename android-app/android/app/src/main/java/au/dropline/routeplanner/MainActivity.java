package au.dropline.routeplanner;

import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import androidx.activity.OnBackPressedCallback;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(TextScanPlugin.class);
        registerPlugin(DevicePlugin.class);
        super.onCreate(savedInstanceState);
        fitBetweenSystemBars();
        // Phone Back button: close the app's open screen first (sheet, Settings page, navigation), like the in-app Back buttons.
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (!DevicePlugin.sendBack()) moveTaskToBack(true);
            }
        });
    }

    /** Android 15+ draws apps behind the status and navigation bars. Keep DropLine between them (and above the keyboard),
     *  with the theme's navy behind the bars and light bar icons — the same on every Android version. */
    private void fitBetweenSystemBars() {
        try {
            WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
            final View web = getBridge().getWebView();
            final View parent = (View) web.getParent();
            parent.setBackgroundColor(Color.parseColor("#0E2B4B"));
            ViewCompat.setOnApplyWindowInsetsListener(web, (v, insets) -> {
                Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
                Insets ime = insets.getInsets(WindowInsetsCompat.Type.ime());
                ViewGroup.MarginLayoutParams lp = (ViewGroup.MarginLayoutParams) v.getLayoutParams();
                lp.topMargin = bars.top;
                lp.leftMargin = bars.left;
                lp.rightMargin = bars.right;
                lp.bottomMargin = Math.max(bars.bottom, ime.bottom);
                v.setLayoutParams(lp);
                return WindowInsetsCompat.CONSUMED;
            });
            WindowInsetsControllerCompat bars = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
            bars.setAppearanceLightStatusBars(false);
            bars.setAppearanceLightNavigationBars(false);
            ViewCompat.requestApplyInsets(web);
        } catch (Exception e) {
            // never block the app from opening because of the bar colours
        }
    }
}
