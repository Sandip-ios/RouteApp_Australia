import Foundation
import UIKit
import Vision
import Capacitor

/// On-device text recognition with Apple's Vision framework (built into iOS, free, works offline).
/// Same result shape as the Android plugin: lines of text with their position in the photo.
@objc(TextScanPlugin)
public class TextScanPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "TextScanPlugin"
    public let jsName = "TextScan"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "recognize", returnType: CAPPluginReturnPromise)
    ]

    @objc func recognize(_ call: CAPPluginCall) {
        guard var data = call.getString("image"), !data.isEmpty else { call.reject("No image"); return }
        if data.hasPrefix("data:"), let comma = data.firstIndex(of: ",") { data = String(data[data.index(after: comma)...]) }
        guard let bytes = Data(base64Encoded: data, options: .ignoreUnknownCharacters),
              let image = UIImage(data: bytes), let cg = image.cgImage else { call.reject("Could not read the photo"); return }
        DispatchQueue.global(qos: .userInitiated).async {
            let started = Date()
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = false          // house numbers and codes must not be "corrected"
            request.recognitionLanguages = ["en-US"]
            let handler = VNImageRequestHandler(cgImage: cg, orientation: .up, options: [:])
            do { try handler.perform([request]) } catch { call.reject("Text recognition failed: \(error.localizedDescription)"); return }
            let W = Double(cg.width), H = Double(cg.height)
            var lines: [[String: Any]] = []
            for obs in request.results ?? [] {
                guard let top = obs.topCandidates(1).first else { continue }
                let b = obs.boundingBox                       // normalised, origin at bottom-left
                lines.append([
                    "text": top.string,
                    "x": Int(b.minX * W), "y": Int((1 - b.maxY) * H),
                    "w": Int(b.width * W), "h": Int(b.height * H)
                ])
            }
            call.resolve([
                "lines": lines, "width": Int(W), "height": Int(H),
                "ms": Int(Date().timeIntervalSince(started) * 1000)
            ])
        }
    }
}

/// The app's main screen: Capacitor's web view plus the text recognition plugin.
@objc(DroplineViewController)
public class DroplineViewController: CAPBridgeViewController {
    public override func capacitorDidLoad() {
        bridge?.registerPluginInstance(TextScanPlugin())
    }
}
