import Foundation
import UIKit
import CoreLocation
import UserNotifications
import Capacitor

/// Small phone helpers for Dropline: permission status, open the app's Settings page, local notifications, clear the icon badge.
@objc(DevicePlugin)
public class DevicePlugin: CAPPlugin, CAPBridgedPlugin, UNUserNotificationCenterDelegate {
    public let identifier = "DevicePlugin"
    public let jsName = "DroplineDevice"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "permissions", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "requestNotifications", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "openSettings", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "notify", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "clearBadge", returnType: CAPPluginReturnPromise)
    ]
    private let locMgr = CLLocationManager()

    public override func load() {
        UNUserNotificationCenter.current().delegate = self      // show notifications even while the app is open
    }
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

    @objc func clearBadge(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            if #available(iOS 16.0, *) { UNUserNotificationCenter.current().setBadgeCount(0) { _ in } }
            else { UIApplication.shared.applicationIconBadgeNumber = 0 }
            UNUserNotificationCenter.current().removeAllDeliveredNotifications()
            call.resolve()
        }
    }
}
