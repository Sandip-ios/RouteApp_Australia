package au.dropline.routeplanner;

import android.os.Bundle;
import androidx.activity.OnBackPressedCallback;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(TextScanPlugin.class);
        registerPlugin(DevicePlugin.class);
        super.onCreate(savedInstanceState);
        // Phone Back button: close the app's open screen first (sheet, Settings page, navigation), like the in-app Back buttons.
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (!DevicePlugin.sendBack()) moveTaskToBack(true);
            }
        });
    }
}
