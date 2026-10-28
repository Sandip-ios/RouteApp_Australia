import Foundation
import UIKit
import CoreLocation
import UserNotifications
import Capacitor

/// Small phone helpers for Dropline: permission status, open the app's Settings page, local notifications, clear the icon badge.
@objc(DevicePlugin)
public class DevicePlugin: CAPPlugin, CAPBridgedPlugin, UNUserNotificationCenterDelegate, CLLocationManagerDelegate {
    public let identifier = "DevicePlugin"
    public let jsName = "DroplineDevice"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "permissions", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "requestNotifications", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "openSettings", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "notify", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "clearBadge", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "requestLocation", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getPosition", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "startUpdates", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "stopUpdates", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "openChat", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "shareFile", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "shareData", returnType: CAPPluginReturnPromise)
    ]
    private let locMgr = CLLocationManager()
    // Location straight from iOS (one permission prompt; the web view's own location prompt is never used)
    private var lastFix: CLLocation?
    private var waiting: [CAPPluginCall] = []
    private var authWaiting: [CAPPluginCall] = []
    private var watching = false

    public override func load() {
        UNUserNotificationCenter.current().delegate = self      // show notifications even while the app is open
        DispatchQueue.main.async {
            self.locMgr.delegate = self
            self.locMgr.desiredAccuracy = kCLLocationAccuracyBest
            self.locMgr.distanceFilter = kCLDistanceFilterNone
        }
    }
    private func fixDict(_ l: CLLocation) -> [String: Any] {
        return ["lat": l.coordinate.latitude, "lon": l.coordinate.longitude, "acc": l.horizontalAccuracy,
                "speed": l.speed >= 0 ? l.speed as Any : NSNull() as Any, "heading": l.course >= 0 ? l.course as Any : NSNull() as Any,
                "time": l.timestamp.timeIntervalSince1970 * 1000]
    }
    private func authStatus() -> CLAuthorizationStatus {
        if #available(iOS 14.0, *) { return locMgr.authorizationStatus } else { return CLLocationManager.authorizationStatus() }
    }
    @objc func requestLocation(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            if self.authStatus() == .notDetermined { self.authWaiting.append(call); self.locMgr.requestWhenInUseAuthorization() }
            else { call.resolve(["location": self.locationState()]) }
        }
    }
    @objc func getPosition(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            let st = self.authStatus()
            if st == .denied || st == .restricted { call.reject("Location is off for DropLine", "1"); return }
            let maxAge = Double(call.getInt("maximumAge") ?? 5000) / 1000
            if let f = self.lastFix, -f.timestamp.timeIntervalSinceNow <= maxAge { call.resolve(self.fixDict(f)); return }
            self.waiting.append(call)
            if st == .notDetermined { self.locMgr.requestWhenInUseAuthorization() } else { self.locMgr.startUpdatingLocation() }
            let ms = call.getInt("timeout") ?? 20000
            DispatchQueue.main.asyncAfter(deadline: .now() + .milliseconds(ms)) {
                if let i = self.waiting.firstIndex(where: { $0 === call }) { self.waiting.remove(at: i); call.reject("Location timed out", "3"); self.stopIfIdle() }
            }
        }
    }
    @objc func startUpdates(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.watching = true
            if self.authStatus() == .notDetermined { self.locMgr.requestWhenInUseAuthorization() } else { self.locMgr.startUpdatingLocation() }
            call.resolve()
        }
    }
    @objc func stopUpdates(_ call: CAPPluginCall) {
        DispatchQueue.main.async { self.watching = false; self.stopIfIdle(); call.resolve() }
    }
    private func stopIfIdle() { if !watching && waiting.isEmpty { locMgr.stopUpdatingLocation() } }
    public func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let l = locations.last else { return }
        lastFix = l
        let calls = waiting; waiting.removeAll()
        for c in calls { c.resolve(fixDict(l)) }
        stopIfIdle()
    }
    public func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        if let e = error as? CLError, e.code == .denied {
            let calls = waiting; waiting.removeAll(); for c in calls { c.reject("Location is off for DropLine", "1") }
            stopIfIdle()
        }
    }
    private func authChanged() {
        let st = authStatus()
        if st == .notDetermined { return }
        let calls = authWaiting; authWaiting.removeAll(); for c in calls { c.resolve(["location": locationState()]) }
        if st == .denied || st == .restricted {
            let w = waiting; waiting.removeAll(); for c in w { c.reject("Location is off for DropLine", "1") }
        } else if !waiting.isEmpty || watching { locMgr.startUpdatingLocation() }
    }
    public func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) { authChanged() }
    public func locationManager(_ manager: CLLocationManager, didChangeAuthorization status: CLAuthorizationStatus) { authChanged() }
    public func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                       withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        if #available(iOS 14.0, *) { completionHandler([.banner, .sound]) } else { completionHandler([.alert, .sound]) }
    }

    private func locationState() -> String {
        let s: CLAuthorizationStatus
        if #available(iOS 14.0, *) { s = locMgr.authorizationStatus } else { s = CLLocationManager.authorizationStatus() }
        switch s {
        case .authorizedAlways, .authorizedWhenInUse: return "granted"
        case .notDetermined: return "prompt"
        default: return "denied"
        }
    }

    @objc func permissions(_ call: CAPPluginCall) {
        let loc = locationState()
        UNUserNotificationCenter.current().getNotificationSettings { st in
            let n: String
            switch st.authorizationStatus {
            case .authorized, .provisional, .ephemeral: n = "granted"
            case .notDetermined: n = "prompt"
            default: n = "denied"
            }
            call.resolve(["location": loc, "notifications": n, "platform": "ios"])
        }
    }

    @objc func requestNotifications(_ call: CAPPluginCall) {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { ok, _ in   // no badge numbers
            call.resolve(["notifications": ok ? "granted" : "denied"])
        }
    }

    @objc func openSettings(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard let url = URL(string: UIApplication.openSettingsURLString) else { call.reject("No Settings"); return }
            UIApplication.shared.open(url, options: [:]) { ok in ok ? call.resolve() : call.reject("Could not open Settings") }
        }
    }

    @objc func notify(_ call: CAPPluginCall) {
        let c = UNMutableNotificationContent()
        c.title = call.getString("title") ?? "Dropline"
        c.body = call.getString("body") ?? ""
        c.sound = .default
        let req = UNNotificationRequest(identifier: "dropline-\(call.getInt("id") ?? 1)", content: c, trigger: nil)
        UNUserNotificationCenter.current().add(req) { err in err == nil ? call.resolve() : call.reject("Notifications are off") }
    }

    /// Chat with the developer: WhatsApp when it is installed, otherwise Messages.
    /// Share a small text file (a route) through the iPhone Share sheet: Save to Files, WhatsApp, Mail…
    @objc func shareFile(_ call: CAPPluginCall) {
        let name = (call.getString("name") ?? "dropline-route.json").replacingOccurrences(of: "/", with: "-")
        let text = call.getString("text") ?? ""
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(name)
        do { try text.write(to: url, atomically: true, encoding: .utf8) } catch { call.reject("Could not prepare the file"); return }
        DispatchQueue.main.async {
            guard let vc = self.bridge?.viewController else { call.reject("No screen to show sharing"); return }
            let sheet = UIActivityViewController(activityItems: [url], applicationActivities: nil)
            sheet.popoverPresentationController?.sourceView = vc.view
            sheet.popoverPresentationController?.sourceRect = CGRect(x: vc.view.bounds.midX, y: vc.view.bounds.maxY - 40, width: 1, height: 1)
            sheet.completionWithItemsHandler = { _, completed, _, _ in call.resolve(["shared": completed]) }
            vc.present(sheet, animated: true)
        }
    }

    /// Share a file made in the app (e.g. the PDF run report), sent as base64.
    @objc func shareData(_ call: CAPPluginCall) {
        let name = (call.getString("name") ?? "dropline-report.pdf").replacingOccurrences(of: "/", with: "-")
        guard let b64 = call.getString("base64"), let data = Data(base64Encoded: b64, options: .ignoreUnknownCharacters) else { call.reject("No file data"); return }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(name)
        do { try data.write(to: url, options: .atomic) } catch { call.reject("Could not prepare the file"); return }
        DispatchQueue.main.async {
            guard let vc = self.bridge?.viewController else { call.reject("No screen to show sharing"); return }
            let sheet = UIActivityViewController(activityItems: [url], applicationActivities: nil)
            sheet.popoverPresentationController?.sourceView = vc.view
            sheet.popoverPresentationController?.sourceRect = CGRect(x: vc.view.bounds.midX, y: vc.view.bounds.maxY - 40, width: 1, height: 1)
            sheet.completionWithItemsHandler = { _, completed, _, _ in call.resolve(["shared": completed]) }
            vc.present(sheet, animated: true)
        }
    }

    @objc func openChat(_ call: CAPPluginCall) {
        let phone = call.getString("phone") ?? "", text = call.getString("text") ?? ""
        let enc = text.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? ""
        DispatchQueue.main.async {
            if let wa = URL(string: "whatsapp://send?phone=\(phone)&text=\(enc)"), UIApplication.shared.canOpenURL(wa) {
                UIApplication.shared.open(wa, options: [:]) { ok in ok ? call.resolve(["app": "whatsapp"]) : call.reject("Could not open WhatsApp") }
            } else if let sms = URL(string: "sms:+\(phone)&body=\(enc)") {
                UIApplication.shared.open(sms, options: [:]) { ok in ok ? call.resolve(["app": "sms"]) : call.reject("Could not open Messages") }
            } else { call.reject("Could not open a chat") }
        }
    }

    @objc func clearBadge(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            if #available(iOS 16.0, *) { UNUserNotificationCenter.current().setBadgeCount(0) { _ in } }
            else { UIApplication.shared.applicationIconBadgeNumber = 0 }
            UNUserNotificationCenter.current().removeAllDeliveredNotifications()
            call.resolve()
        }
    }
}
