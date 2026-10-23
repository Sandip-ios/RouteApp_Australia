package au.dropline.routeplanner;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Rect;
import android.os.SystemClock;
import android.util.Base64;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

/** On-device text recognition (Google ML Kit, bundled model: works offline, no cost). */
@CapacitorPlugin(name = "TextScan")
public class TextScanPlugin extends Plugin {
    private TextRecognizer recognizer;

    @Override
    public void load() {
        recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
    }

    @PluginMethod
    public void recognize(PluginCall call) {
        String data = call.getString("image");
        if (data == null || data.isEmpty()) { call.reject("No image"); return; }
        int comma = data.indexOf(',');
        if (data.startsWith("data:") && comma > 0) data = data.substring(comma + 1);
        final Bitmap bmp;
        try {
            byte[] bytes = Base64.decode(data, Base64.DEFAULT);
            bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        } catch (Exception e) { call.reject("Could not read the photo"); return; }
        if (bmp == null) { call.reject("Could not read the photo"); return; }
        final long t0 = SystemClock.elapsedRealtime();
        recognizer.process(InputImage.fromBitmap(bmp, 0))
            .addOnSuccessListener(text -> {
                JSArray lines = new JSArray();
                for (Text.TextBlock block : text.getTextBlocks()) {
                    for (Text.Line line : block.getLines()) {
                        Rect r = line.getBoundingBox();
                        if (r == null) continue;
                        JSObject o = new JSObject();
                        o.put("text", line.getText());
                        o.put("x", r.left); o.put("y", r.top); o.put("w", r.width()); o.put("h", r.height());
                        lines.put(o);
                    }
                }
                JSObject ret = new JSObject();
                ret.put("lines", lines);
                ret.put("width", bmp.getWidth());
                ret.put("height", bmp.getHeight());
                ret.put("ms", SystemClock.elapsedRealtime() - t0);
                call.resolve(ret);
            })
            .addOnFailureListener(e -> call.reject("Text recognition failed: " + e.getMessage()));
    }
}
