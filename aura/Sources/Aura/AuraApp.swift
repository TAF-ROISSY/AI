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

/// Tous les moteurs d'Aura, créés une seule fois.
/// Ils ne sont pas observés par l'App elle-même : seules les vues qui les utilisent
/// se rafraîchissent quand ils changent.
@MainActor
final class AppModel {
    static let shared = AppModel()
    let router = Router()
    let cleanup = CleanupEngine()
    let monitor = SystemMonitor.shared
    let apps = AppManager()
    let files = FileTools()
    let volumes = VolumeManager()
    let security = SecurityScanner()
    let privacy = PrivacyManager()
    let permissions = PermissionsManager()
    let maintenance = MaintenanceManager()
    let updater = UpdateManager()
    let extensions = ExtensionManager()
    let similar = SimilarImageFinder()
    let cloud = CloudManager()
    let health = HealthCenter()
    let selfUpdate = SelfUpdater()
    let guardian = Guardian()
    let net = NetworkTools()
    let disks = DiskTools()
    let batteryHistory = BatteryHistory()
    let keepAwake = KeepAwake()
    let tidy = TidyManager()
    let activity = AppActivityMonitor()
    /// Lu une fois au lancement (modifiable dans les Réglages, effectif au prochain lancement).
    let showMenuBar = UserDefaults.standard.object(forKey: "aura.menuBarEnabled") as? Bool ?? true
    private var started = false

    func startServices() {
        guard !started else { return }
        started = true
        monitor.start()
        health.start(monitor: monitor, cleanup: cleanup)
        selfUpdate.start()
        guardian.start(health: health)
        activity.start()
        activity.onGreedy = { [weak self] app, text in
            self?.health.report(HealthAlert(id: "app-\(app.id)", title: "\(app.name) est gourmande",
                                            message: text, icon: "flame.fill", color: .orange, module: .activity))
        }
        health.onSlowTick = { [weak self] in
            guard let self else { return }
            self.batteryHistory.record(self.monitor.battery)
            await self.tidy.autoRunIfDue { title, body in self.health.notify(title, body) }
        }
    }
}

extension View {
    func withAuraModel(_ m: AppModel) -> some View {
        self.environmentObject(m.router)
            .environmentObject(m.cleanup)
            .environmentObject(m.monitor)
            .environmentObject(m.apps)
            .environmentObject(m.files)
            .environmentObject(m.volumes)
            .environmentObject(m.security)
            .environmentObject(m.privacy)
            .environmentObject(m.permissions)
            .environmentObject(m.maintenance)
            .environmentObject(m.updater)
            .environmentObject(m.extensions)
            .environmentObject(m.similar)
            .environmentObject(m.cloud)
            .environmentObject(m.health)
            .environmentObject(m.selfUpdate)
            .environmentObject(m.guardian)
            .environmentObject(m.net)
            .environmentObject(m.disks)
            .environmentObject(m.batteryHistory)
            .environmentObject(m.keepAwake)
            .environmentObject(m.tidy)
            .environmentObject(m.activity)
    }
}

@main
struct AuraApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    private let model = AppModel.shared

    var body: some Scene {
        WindowGroup("Aura", id: "main") {
            ContentView()
                .withAuraModel(model)
                .frame(minWidth: 1180, minHeight: 760)
                .preferredColorScheme(.dark)
                .onAppear { model.startServices() }
        }
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(after: .appInfo) {
                Button("Rechercher des mises à jour…") { Task { await model.selfUpdate.check(silent: false) } }
            }
            CommandMenu("Aura") {
                Button("Analyse intelligente") { model.router.open(.smartScan) }.keyboardShortcut("1")
                Button("Déchets système") { model.router.open(.cleanup) }.keyboardShortcut("2")
                Button("Sécurité") { model.router.open(.security) }.keyboardShortcut("3")
                Button("Surveillance") { model.router.open(.monitor) }.keyboardShortcut("4")
                Button("Applications actives") { model.router.open(.activity) }.keyboardShortcut("6")
                Button("Carte de l'espace") { model.router.open(.spaceMap) }.keyboardShortcut("5")
                Divider()
                Button("Rester éveillé 1 h / arrêter") {
                    if model.keepAwake.isActive { model.keepAwake.deactivate() } else { model.keepAwake.activate(minutes: 60) }
                }
            }
        }

        MenuBarExtra(isInserted: .constant(model.showMenuBar)) {
            MenuBarView()
                .withAuraModel(model)
                .auraChrome()
                .background(AuraTheme.fuselage)
                .preferredColorScheme(.dark)
                .onAppear { model.startServices() }
        } label: {
            Image(systemName: "sparkles")
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
                .withAuraModel(model)
                .auraChrome()
                .preferredColorScheme(.dark)
        }
    }
}
