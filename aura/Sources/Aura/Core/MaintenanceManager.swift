import Foundation
import AppKit

struct MaintenanceTask: Identifiable {
    let id: String
    let name: String
    let detail: String
    let icon: String
    let needsAdmin: Bool
    let recommendAfterDays: Int     // recommandée si jamais lancée depuis N jours
    /// Commande non privilégiée (exécutée en Swift) ou commande shell admin.
    let local: (() -> Bool)?
    let adminCommand: String?
    var selected = false
}

@MainActor
final class MaintenanceManager: ObservableObject {
    @Published var tasks: [MaintenanceTask] = []
    @Published var running: String?
    @Published var log: [String] = []
    @Published var snapshots: [String] = []

    private let lastRunKey = "aura.maintenance.lastRun"

    init() {
        tasks = Self.catalog()
        for i in tasks.indices { tasks[i].selected = isRecommended(tasks[i]) }
    }

    nonisolated static func catalog() -> [MaintenanceTask] {
        let lsregister = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
        return [
            MaintenanceTask(id: "ram", name: "Libérer la mémoire vive", detail: "Purge la mémoire inactive pour donner de l'air aux apps ouvertes.",
                            icon: "memorychip", needsAdmin: true, recommendAfterDays: 0, local: nil,
                            adminCommand: "/usr/sbin/purge"),
            MaintenanceTask(id: "dns", name: "Vider le cache DNS", detail: "Règle les sites qui ne s'ouvrent plus ou pointent vers une ancienne adresse.",
                            icon: "network", needsAdmin: true, recommendAfterDays: 30, local: nil,
                            adminCommand: "/usr/bin/dscacheutil -flushcache; /usr/bin/killall -HUP mDNSResponder"),
            MaintenanceTask(id: "scripts", name: "Exécuter les scripts de maintenance", detail: "Rotation des journaux et nettoyage des fichiers temporaires système.",
                            icon: "scroll", needsAdmin: true, recommendAfterDays: 14, local: nil,
                            adminCommand: "if [ -x /usr/sbin/periodic ]; then /usr/sbin/periodic daily weekly monthly; fi; true"),
            MaintenanceTask(id: "launchservices", name: "Reconstruire la base Launch Services",
                            detail: "Supprime les doublons du menu « Ouvrir avec » et répare les icônes et associations de fichiers.",
                            icon: "square.stack.3d.up", needsAdmin: false, recommendAfterDays: 60,
                            local: { Shell.run(lsregister, ["-kill", "-r", "-domain", "local", "-domain", "system", "-domain", "user"], timeout: 300).status == 0 },
                            adminCommand: nil),
            MaintenanceTask(id: "spotlight", name: "Réindexer Spotlight", detail: "Utile si la recherche est lente ou ne trouve plus tes fichiers. L'indexation prend un moment.",
                            icon: "magnifyingglass", needsAdmin: true, recommendAfterDays: 120, local: nil,
                            adminCommand: "/usr/bin/mdutil -E /"),
            MaintenanceTask(id: "mail", name: "Accélérer Mail", detail: "Compacte la base de données de Mail (Mail doit être fermé).",
                            icon: "envelope", needsAdmin: false, recommendAfterDays: 60,
                            local: {
                                guard NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.mail").isEmpty else { return false }
                                let dbs = FS.children(FS.url("~/Library/Mail")).filter { $0.lastPathComponent.hasPrefix("V") }
                                    .map { $0.appendingPathComponent("MailData/Envelope Index") }.filter(FS.exists)
                                return dbs.allSatisfy { Shell.run("/usr/bin/sqlite3", [$0.path, "VACUUM;"], timeout: 600).status == 0 }
                            }, adminCommand: nil),
            MaintenanceTask(id: "quicklook", name: "Reconstruire Coup d'œil", detail: "Répare les aperçus et vignettes qui ne s'affichent plus.",
                            icon: "eye", needsAdmin: false, recommendAfterDays: 90,
                            local: { Shell.run("/usr/bin/qlmanage", ["-r"]).status == 0 && Shell.run("/usr/bin/qlmanage", ["-r", "cache"]).status == 0 },
                            adminCommand: nil),
            MaintenanceTask(id: "fonts", name: "Vider le cache des polices", detail: "Corrige les polices qui s'affichent mal. Redémarrage conseillé ensuite.",
                            icon: "textformat", needsAdmin: false, recommendAfterDays: 365,
                            local: { Shell.run("/usr/bin/atsutil", ["databases", "-removeUser"]).status == 0 },
                            adminCommand: nil),
            MaintenanceTask(id: "snapshots", name: "Alléger les instantanés Time Machine",
                            detail: "Supprime les instantanés locaux qui gonflent « Données du système ».",
                            icon: "clock.arrow.circlepath", needsAdmin: true, recommendAfterDays: 30, local: nil,
                            adminCommand: "/usr/bin/tmutil thinlocalsnapshots / 999999999999 4"),
            MaintenanceTask(id: "permissions", name: "Réparer les autorisations du dossier personnel",
                            detail: "Corrige les erreurs « accès refusé » dans ton dossier.",
                            icon: "person.badge.key", needsAdmin: true, recommendAfterDays: 365, local: nil,
                            adminCommand: "/usr/sbin/diskutil resetUserPermissions / \(getuid())"),
            MaintenanceTask(id: "verify", name: "Vérifier le disque de démarrage", detail: "Contrôle la structure du disque (lecture seule, sans risque).",
                            icon: "checkmark.seal", needsAdmin: false, recommendAfterDays: 90,
                            local: { Shell.run("/usr/sbin/diskutil", ["verifyVolume", "/"], timeout: 900).status == 0 },
                            adminCommand: nil),
            MaintenanceTask(id: "ui", name: "Relancer le Dock, le Finder et la barre des menus",
                            detail: "Débloque une interface figée sans redémarrer.",
                            icon: "dock.rectangle", needsAdmin: false, recommendAfterDays: 0,
                            local: { ["Dock", "Finder", "SystemUIServer", "ControlCenter"].forEach { Shell.run("/usr/bin/killall", [$0], timeout: 5) }; return true },
                            adminCommand: nil)
        ]
    }

    func lastRun(_ t: MaintenanceTask) -> Date? {
        let d = UserDefaults.standard.dictionary(forKey: lastRunKey) as? [String: Double] ?? [:]
        return d[t.id].map { Date(timeIntervalSince1970: $0) }
    }

    func isRecommended(_ t: MaintenanceTask) -> Bool {
        guard t.recommendAfterDays > 0 else { return false }
        guard let last = lastRun(t) else { return true }
        return Date().timeIntervalSince(last) > Double(t.recommendAfterDays) * 86400
    }

    var recommendedCount: Int { tasks.filter(isRecommended).count }

    private func markRun(_ id: String) {
        var d = UserDefaults.standard.dictionary(forKey: lastRunKey) as? [String: Double] ?? [:]
        d[id] = Date().timeIntervalSince1970
        UserDefaults.standard.set(d, forKey: lastRunKey)
    }

    func toggle(_ id: String) {
        if let i = tasks.firstIndex(where: { $0.id == id }) { tasks[i].selected.toggle() }
    }

    func selectRecommended() {
        for i in tasks.indices { tasks[i].selected = isRecommended(tasks[i]) }
    }

    /// Exécute les tâches cochées : un seul mot de passe pour toutes les tâches admin.
    func runSelected() async {
        let selected = tasks.filter(\.selected)
        guard !selected.isEmpty else { return }
        log = []
        let admin = selected.filter { $0.adminCommand != nil }
        if !admin.isEmpty {
            running = admin.map(\.name).joined(separator: ", ")
            let script = admin.compactMap(\.adminCommand).joined(separator: "; ")
            let r = Shell.admin(script)
            for t in admin {
                log.append((r.ok ? "✅ " : "⚠️ ") + t.name + (r.ok ? "" : " — annulé"))
                if r.ok { markRun(t.id) }
            }
        }
        for t in selected where t.local != nil {
            running = t.name
            let fn = t.local!
            let ok = await Task.detached { fn() }.value
            log.append((ok ? "✅ " : "⚠️ ") + t.name + (ok ? "" : (t.id == "mail" ? " — ferme Mail puis réessaie" : " — échec")))
            if ok { markRun(t.id) }
        }
        running = nil
        for i in tasks.indices { tasks[i].selected = false }
        objectWillChange.send()
    }

    func loadSnapshots() async {
        let out = await Task.detached { Shell.run("/usr/bin/tmutil", ["listlocalsnapshots", "/"], timeout: 20).output }.value
        snapshots = out.split(separator: "\n").map(String.init).filter { $0.contains("com.apple") }
    }
}
