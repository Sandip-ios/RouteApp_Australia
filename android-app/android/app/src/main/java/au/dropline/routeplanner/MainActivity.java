package au.dropline.routeplanner;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(TextScanPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
