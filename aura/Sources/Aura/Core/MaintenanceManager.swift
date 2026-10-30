import Foundation
import AppKit

/// Résultat d'une tâche : réussite + explication courte.
typealias TaskOutcome = (ok: Bool, message: String)

struct MaintenanceTask: Identifiable {
    let id: String
    let name: String
    let detail: String
    let icon: String
    let recommendAfterDays: Int          // recommandée si jamais lancée depuis N jours
    /// Tâche sans droits particuliers, exécutée en arrière-plan.
    let local: (() -> TaskOutcome)?
    /// Tâche nécessitant le mot de passe administrateur (commande shell).
    let adminCommand: String?
    var selected = false
    var needsAdmin: Bool { adminCommand != nil }
}

enum TaskState: Equatable {
    case idle, running, done(String), failed(String)
}

@MainActor
final class MaintenanceManager: ObservableObject {
    @Published var tasks: [MaintenanceTask] = []
    @Published var states: [String: TaskState] = [:]
    @Published var isRunning = false
    @Published var summary = ""
    @Published var snapshots: [String] = []

    private let lastRunKey = "aura.maintenance.lastRun"

    init() {
        tasks = Self.catalog()
        for i in tasks.indices { tasks[i].selected = isRecommended(tasks[i]) }
    }

    // MARK: Catalogue

    nonisolated static func tool(_ path: String) -> Bool { FileManager.default.isExecutableFile(atPath: path) }

    /// Exécute une commande et transforme le résultat en message lisible.
    nonisolated static func exec(_ path: String, _ args: [String], timeout: TimeInterval = 600,
                                 success: String) -> TaskOutcome {
        guard tool(path) else { return (false, "Outil absent de cette version de macOS") }
        let r = Shell.run(path, args, timeout: timeout)
        if r.status == 0 { return (true, success) }
        let last = r.output.split(separator: "\n").last.map(String.init) ?? "code \(r.status)"
        return (false, last)
    }

    nonisolated static func catalog() -> [MaintenanceTask] {
        let lsregister = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
        return [
            MaintenanceTask(id: "ram", name: "Libérer la mémoire vive",
                            detail: "Purge la mémoire inactive pour donner de l'air aux apps ouvertes.",
                            icon: "memorychip", recommendAfterDays: 0, local: nil,
                            adminCommand: "/usr/sbin/purge"),
            MaintenanceTask(id: "dns", name: "Vider le cache DNS",
                            detail: "Règle les sites qui ne s'ouvrent plus ou pointent vers une ancienne adresse.",
                            icon: "network", recommendAfterDays: 30, local: nil,
                            adminCommand: "/usr/bin/dscacheutil -flushcache && /usr/bin/killall -HUP mDNSResponder"),
            MaintenanceTask(id: "scripts", name: "Exécuter les scripts de maintenance",
                            detail: "Rotation des journaux et nettoyage des fichiers temporaires du système.",
                            icon: "scroll", recommendAfterDays: 14, local: nil,
                            adminCommand: "if [ -x /usr/sbin/periodic ]; then /usr/sbin/periodic daily weekly monthly; else /usr/sbin/newsyslog -F; fi"),
            MaintenanceTask(id: "launchservices", name: "Reconstruire la base Launch Services",
                            detail: "Supprime les doublons du menu « Ouvrir avec » et répare icônes et associations de fichiers.",
                            icon: "square.stack.3d.up", recommendAfterDays: 60,
                            local: { MaintenanceManager.exec(lsregister, ["-kill", "-r", "-domain", "local", "-domain", "system", "-domain", "user"],
                                          timeout: 600, success: "Base reconstruite") },
                            adminCommand: nil),
            MaintenanceTask(id: "spotlight", name: "Réindexer Spotlight",
                            detail: "Utile si la recherche est lente ou ne trouve plus tes fichiers. L'indexation continue ensuite en arrière-plan.",
                            icon: "magnifyingglass", recommendAfterDays: 120, local: nil,
                            adminCommand: "/usr/bin/mdutil -E /"),
            MaintenanceTask(id: "mail", name: "Accélérer Mail",
                            detail: "Compacte la base de données de Mail (Mail doit être fermé).",
                            icon: "envelope", recommendAfterDays: 60,
                            local: {
                                guard NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.mail").isEmpty else {
                                    return (false, "Ferme Mail puis relance la tâche")
                                }
                                let dbs = FS.children(FS.url("~/Library/Mail")).filter { $0.lastPathComponent.hasPrefix("V") }
                                    .map { $0.appendingPathComponent("MailData/Envelope Index") }.filter(FS.exists)
                                guard !dbs.isEmpty else {
                                    return (false, FS.hasFullDiskAccess ? "Aucune base Mail trouvée" : "Accès complet au disque requis")
                                }
                                let before = dbs.reduce(Int64(0)) { $0 + FS.fileSize($1) }
                                for db in dbs where Shell.run("/usr/bin/sqlite3", [db.path, "VACUUM;"], timeout: 900).status != 0 {
                                    return (false, "Base Mail verrouillée")
                                }
                                let after = dbs.reduce(Int64(0)) { $0 + FS.fileSize($1) }
                                return (true, "Base compactée (\(Fmt.bytes(max(0, before - after))) gagnés)")
                            }, adminCommand: nil),
            MaintenanceTask(id: "quicklook", name: "Reconstruire Coup d'œil",
                            detail: "Répare les aperçus et vignettes qui ne s'affichent plus.",
                            icon: "eye", recommendAfterDays: 90,
                            local: {
                                _ = Shell.run("/usr/bin/qlmanage", ["-r"], timeout: 60)
                                return MaintenanceManager.exec("/usr/bin/qlmanage", ["-r", "cache"], timeout: 60, success: "Cache des aperçus vidé")
                            }, adminCommand: nil),
            MaintenanceTask(id: "fonts", name: "Vider le cache des polices",
                            detail: "Corrige les polices qui s'affichent mal. Un redémarrage du Mac est conseillé ensuite.",
                            icon: "textformat", recommendAfterDays: 365, local: nil,
                            adminCommand: "if [ -x /usr/bin/atsutil ]; then /usr/bin/atsutil databases -remove; fi; /bin/rm -rf /private/var/folders/*/*/C/com.apple.FontRegistry 2>/dev/null; true"),
            MaintenanceTask(id: "snapshots", name: "Alléger les instantanés Time Machine",
                            detail: "Supprime les instantanés locaux qui gonflent « Données du système ».",
                            icon: "clock.arrow.circlepath", recommendAfterDays: 30, local: nil,
                            adminCommand: "/usr/bin/tmutil thinlocalsnapshots / 999999999999 4"),
            MaintenanceTask(id: "permissions", name: "Réparer les autorisations du dossier personnel",
                            detail: "Corrige les erreurs « accès refusé » dans ton dossier. Peut prendre plusieurs minutes.",
                            icon: "person.badge.key", recommendAfterDays: 365, local: nil,
                            adminCommand: "/usr/sbin/diskutil resetUserPermissions / \(getuid())"),
            MaintenanceTask(id: "verify", name: "Vérifier le disque de démarrage",
                            detail: "Contrôle la structure du disque, en lecture seule et sans risque.",
                            icon: "checkmark.seal", recommendAfterDays: 90,
                            local: { MaintenanceManager.exec("/usr/sbin/diskutil", ["verifyVolume", "/"], timeout: 1800, success: "Disque en bon état") },
                            adminCommand: nil),
            MaintenanceTask(id: "ui", name: "Relancer le Dock, le Finder et la barre des menus",
                            detail: "Débloque une interface figée sans redémarrer le Mac.",
                            icon: "dock.rectangle", recommendAfterDays: 0,
                            local: {
                                ["Dock", "Finder", "SystemUIServer", "ControlCenter"].forEach { Shell.run("/usr/bin/killall", [$0], timeout: 5) }
                                return (true, "Interface relancée")
                            }, adminCommand: nil)
        ]
    }

    // MARK: Historique

    func lastRun(_ t: MaintenanceTask) -> Date? {
        let d = UserDefaults.standard.dictionary(forKey: lastRunKey) as? [String: Double] ?? [:]
        return d[t.id].map { Date(timeIntervalSince1970: $0) }
    }

    func isRecommended(_ t: MaintenanceTask) -> Bool {
        guard t.recommendAfterDays > 0 else { return false }
        guard let last = lastRun(t) else { return true }
        return Date().timeIntervalSince(last) > Double(t.recommendAfterDays) * 86400
    }

    var recommendedCount: Int { tasks.filter { isRecommended($0) }.count }

    /// Compatibilité avec l'Analyse intelligente.
    var log: [String] {
        tasks.compactMap { t in
            switch states[t.id] {
            case .done(let m)?: return "✅ \(t.name) — \(m)"
            case .failed(let m)?: return "⚠️ \(t.name) — \(m)"
            default: return nil
            }
        }
    }

    private func markRun(_ id: String) {
        var d = UserDefaults.standard.dictionary(forKey: lastRunKey) as? [String: Double] ?? [:]
        d[id] = Date().timeIntervalSince1970
        UserDefaults.standard.set(d, forKey: lastRunKey)
    }

    func toggle(_ id: String) {
        guard !isRunning, let i = tasks.firstIndex(where: { $0.id == id }) else { return }
        tasks[i].selected.toggle()
    }

    func selectRecommended() {
        for i in tasks.indices { tasks[i].selected = isRecommended(tasks[i]) }
    }

    // MARK: Exécution

    /// Lance les tâches cochées. Les tâches administrateur partagent un seul mot de passe,
    /// mais chacune a son propre résultat (une erreur n'annule pas les autres).
    func runSelected() async {
        let selected = tasks.filter(\.selected)
        guard !selected.isEmpty, !isRunning else { return }
        isRunning = true
        summary = ""
        for t in selected { states[t.id] = .idle }

        let admin = selected.filter { $0.adminCommand != nil }
        if !admin.isEmpty {
            for t in admin { states[t.id] = .running }
            let logDir = "/tmp/aura-maintenance-\(getpid())"
            var script = "mkdir -p \(logDir); chmod 755 \(logDir)"
            for t in admin {
                script += "; ( \(t.adminCommand!) ) > \(logDir)/\(t.id).log 2>&1; echo AURA_RESULT:\(t.id):$?"
            }
            script += "; chmod -R a+r \(logDir); true"
            let r = await Shell.adminAsync(script)
            if !r.ok {
                for t in admin { states[t.id] = .failed(r.output.isEmpty ? "Échec" : r.output) }
            } else {
                var codes: [String: Int] = [:]
                for line in r.output.split(whereSeparator: { $0 == "\n" || $0 == "\r" }) where line.hasPrefix("AURA_RESULT:") {
                    let parts = line.split(separator: ":")
                    if parts.count == 3, let c = Int(parts[2]) { codes[String(parts[1])] = c }
                }
                for t in admin {
                    if codes[t.id] == 0 {
                        states[t.id] = .done("Terminé")
                        markRun(t.id)
                    } else {
                        let out = (try? String(contentsOfFile: "\(logDir)/\(t.id).log", encoding: .utf8)) ?? ""
                        let last = out.split(separator: "\n").last.map(String.init) ?? "code \(codes[t.id] ?? -1)"
                        states[t.id] = .failed(last)
                    }
                }
            }
        }

        for t in selected where t.local != nil {
            states[t.id] = .running
            let fn = t.local!
            let outcome = await Task.detached(priority: .userInitiated) { fn() }.value
            states[t.id] = outcome.ok ? .done(outcome.message) : .failed(outcome.message)
            if outcome.ok { markRun(t.id) }
        }

        let ok = selected.filter { if case .done(_)? = states[$0.id] { return true } else { return false } }.count
        summary = ok == selected.count ? "✅ \(ok) tâche(s) terminée(s)" : "\(ok)/\(selected.count) tâche(s) réussie(s)"
        for i in tasks.indices { tasks[i].selected = false }
        isRunning = false
        await loadSnapshots()
    }

    func loadSnapshots() async {
        let out = await Task.detached { Shell.run("/usr/bin/tmutil", ["listlocalsnapshots", "/"], timeout: 20).output }.value
        snapshots = out.split(separator: "\n").map(String.init).filter { $0.contains("com.apple") }
    }
}
