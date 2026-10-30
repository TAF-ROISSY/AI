import SwiftUI
import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Indispensable quand l'app est lancée via `swift run` (sans bundle .app)
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        // Avec l'icône de barre des menus, Aura reste active pour la surveillance et les alertes
        UserDefaults.standard.object(forKey: "aura.menuBarEnabled") as? Bool == false
    }
}

@main
struct AuraApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var router = Router()
    @StateObject private var cleanup = CleanupEngine()
    @StateObject private var monitor = SystemMonitor.shared
    @StateObject private var apps = AppManager()
    @StateObject private var files = FileTools()
    @StateObject private var volumes = VolumeManager()
    @StateObject private var security = SecurityScanner()
    @StateObject private var privacy = PrivacyManager()
    @StateObject private var permissions = PermissionsManager()
    @StateObject private var maintenance = MaintenanceManager()
    @StateObject private var updater = UpdateManager()
    @StateObject private var extensions = ExtensionManager()
    @StateObject private var similar = SimilarImageFinder()
    @StateObject private var cloud = CloudManager()
    @StateObject private var health = HealthCenter()
    @StateObject private var selfUpdate = SelfUpdater()
    @AppStorage("aura.menuBarEnabled") private var menuBarEnabled = true

    var body: some Scene {
        WindowGroup("Aura", id: "main") {
            ContentView()
                .environmentObject(router)
                .environmentObject(cleanup)
                .environmentObject(monitor)
                .environmentObject(apps)
                .environmentObject(files)
                .environmentObject(volumes)
                .environmentObject(security)
                .environmentObject(privacy)
                .environmentObject(permissions)
                .environmentObject(maintenance)
                .environmentObject(updater)
                .environmentObject(extensions)
                .environmentObject(similar)
                .environmentObject(cloud)
                .environmentObject(health)
                .environmentObject(selfUpdate)
                .frame(minWidth: 1180, minHeight: 760)
                .preferredColorScheme(.dark)
                .onAppear { startServices() }
        }
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(after: .appInfo) {
                Button("Rechercher des mises à jour…") { Task { await selfUpdate.check(silent: false) } }
            }
            CommandMenu("Aura") {
                Button("Analyse intelligente") { router.open(.smartScan) }.keyboardShortcut("1")
                Button("Déchets système") { router.open(.cleanup) }.keyboardShortcut("2")
                Button("Sécurité") { router.open(.security) }.keyboardShortcut("3")
                Button("Surveillance") { router.open(.monitor) }.keyboardShortcut("4")
                Button("Carte de l'espace") { router.open(.spaceMap) }.keyboardShortcut("5")
            }
        }

        MenuBarExtra(isInserted: $menuBarEnabled) {
            MenuBarView()
                .environmentObject(cleanup)
                .environmentObject(monitor)
                .environmentObject(volumes)
                .preferredColorScheme(.dark)
                .onAppear { startServices() }
        } label: {
            Image(systemName: "sparkles")
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
                .environmentObject(cleanup)
                .environmentObject(health)
                .environmentObject(selfUpdate)
                .preferredColorScheme(.dark)
        }
    }

    private func startServices() {
        monitor.start()
        health.start(monitor: monitor, cleanup: cleanup)
        selfUpdate.start()
    }
}
