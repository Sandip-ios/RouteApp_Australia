// Run Apple's Vision text recognition (same settings as the iPhone app) on page images; print JSON lines per page.
import Foundation
import Vision
import CoreGraphics
import ImageIO

var out: [[String: Any]] = []
for path in CommandLine.arguments.dropFirst() {
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let full = CGImageSourceCreateImageAtIndex(src, 0, nil) else { continue }
    // same size the app sends: longest side 1800 px
    let k = min(1.0, 1800.0 / Double(max(full.width, full.height)))
    let W = Int(Double(full.width) * k), H = Int(Double(full.height) * k)
    let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    ctx.interpolationQuality = .high
    ctx.draw(full, in: CGRect(x: 0, y: 0, width: W, height: H))
    let cg = ctx.makeImage()!
    let started = Date()
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    try VNImageRequestHandler(cgImage: cg, orientation: .up, options: [:]).perform([request])
    var lines: [[String: Any]] = []
    for obs in request.results ?? [] {
        guard let top = obs.topCandidates(1).first else { continue }
        let b = obs.boundingBox
        lines.append(["text": top.string, "x": Int(b.minX * Double(W)), "y": Int((1 - b.maxY) * Double(H)), "w": Int(b.width * Double(W)), "h": Int(b.height * Double(H))])
    }
    let ms = Int(Date().timeIntervalSince(started) * 1000)
    FileHandle.standardError.write("\((path as NSString).lastPathComponent): \(lines.count) lines in \(ms) ms\n".data(using: .utf8)!)
    out.append(["file": (path as NSString).lastPathComponent, "size": 1800, "ms": ms, "lines": lines])
}
let data = try JSONSerialization.data(withJSONObject: ["raw": out, "pages": []], options: [])
FileManager.default.createFile(atPath: "results.json", contents: data)
