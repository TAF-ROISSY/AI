import Foundation
import AppKit
import SwiftUI

enum ThreatLevel: Int, Comparable {
    case info = 0, low, medium, high
    static func < (a: ThreatLevel, b: ThreatLevel) -> Bool { a.rawValue < b.rawValue }
    var label: String {
        switch self {
        case .info: return "Info"
        case .low: return "Faible"
        case .medium: return "Moyen"
        case .high: return "Élevé"
        }
    }
    var color: NSColor {
        switch self {
        case .info: return .systemGray
        case .low: return .systemYellow
        case .medium: return .systemOrange
        case .high: return .systemRed
        }
    }
}

enum ThreatKind: String {
    case adware = "Logiciel publicitaire connu"
    case pua = "Application potentiellement indésirable"
    case persistence = "Lancement automatique suspect"
    case unsigned = "Application non signée"
    case extensionRisk = "Extension de navigateur"
    case profile = "Profil de configuration"
    case cron = "Tâche planifiée (cron)"
}

struct Threat: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let title: String
    let detail: String
    let kind: ThreatKind
    let level: ThreatLevel
    var selected: Bool
    var removable = true
    var launchLabel: String?
}

struct SecurityCheck: Identifiable {
    let id: String
    let title: String
    let ok: Bool?
    let detail: String
    let fixHint: String
    let settingsURL: String?
}

enum ScanDepth: String, CaseIterable, Identifiable {
    case quick = "Rapide", balanced = "Équilibrée", deep = "Approfondie"
    var id: String { rawValue }
}

@MainActor
final class SecurityScanner: ObservableObject {
    @Published var checks: [SecurityCheck] = []
    @Published var threats: [Threat] = []
    @Published var isScanning = false
    @Published var progressLabel = ""
    @Published var lastScan: Date?
    @Published var depth: ScanDepth = .balanced
    @Pref("aura.security.ignored") private var ignoredRaw = ""

    private var ignored: Set<String> { Set(ignoredRaw.split(separator: "\n").map(String.init)) }

    /// Noms et identifiants de logiciels publicitaires / indésirables bien connus sur macOS.
    nonisolated static let knownBad: [(String, ThreatKind)] = [
        ("genieo", .adware), ("vsearch", .adware), ("conduit", .adware), ("spigot", .adware),
        ("crossrider", .adware), ("pirrit", .adware), ("shlayer", .adware), ("bundlore", .adware),
        ("searchmine", .adware), ("searchbaron", .adware), ("mughthesec", .adware), ("installcore", .adware),
        ("adload", .adware), ("searchmarquis", .adware), ("searchpulse", .adware), ("chumsearch", .adware),
        ("mackeeper", .pua), ("zeobit", .pua), ("advanced mac cleaner", .pua), ("com.pcv.", .pua),
        ("mac auto fixer", .pua), ("smart mac booster", .pua), ("mac tonic", .pua), ("mac cleanup pro", .pua),
        ("mac mechanic", .pua), ("tuneupmymac", .pua), ("macbooster", .pua)
    ]

    nonisolated static func matchKnown(_ text: String) -> ThreatKind? {
        let t = text.lowercased()
        return knownBad.first { t.contains($0.0) }?.1
    }

    // MARK: État de sécurité du système

    func refreshChecks() async {
        checks = await Task.detached { Self.readChecks() }.value
    }

    nonisolated static func readChecks() -> [SecurityCheck] {
        let sip = Shell.run("/usr/bin/csrutil", ["status"]).output
        let gk = Shell.run("/usr/sbin/spctl", ["--status"]).output
        let fv = Shell.run("/usr/bin/fdesetup", ["status"]).output
        let fw = Shell.run("/usr/libexec/ApplicationFirewall/socketfilterfw", ["--getglobalstate"]).output
        let xpInfo = NSDictionary(contentsOfFile: "/Library/Apple/System/Library/CoreServices/XProtect.bundle/Contents/Info.plist")
        let xpVersion = xpInfo?["CFBundleShortVersionString"] as? String
        let su = NSDictionary(contentsOfFile: "/Library/Preferences/com.apple.SoftwareUpdate.plist")
        let autoCheck = su?["AutomaticCheckEnabled"] as? Bool
        let critical = su?["CriticalUpdateInstall"] as? Bool
        let pending = Shell.run("/usr/sbin/softwareupdate", ["-l", "--no-scan"], timeout: 20).output
        let hasPending = pending.contains("* Label:")

        func yes(_ s: String, _ k: String) -> Bool? { s.isEmpty ? nil : s.lowercased().contains(k) }
        let tm = TimeMachine.status()
        let tmDetail: String = {
            guard tm.configured else { return "Aucun disque de sauvegarde configuré." }
            guard let d = tm.last else { return "Sauvegarde configurée, date de la dernière inconnue." }
            return "Dernière sauvegarde \(Fmt.relativeDate(d))."
        }()
        let tmOK: Bool? = !tm.configured ? false : tm.last.map { Date().timeIntervalSince($0) < 7 * 86400 }

        return [
            SecurityCheck(id: "sip", title: "Protection de l'intégrité du système (SIP)",
                          ok: yes(sip, "enabled"), detail: "Empêche les logiciels de modifier macOS.",
                          fixHint: "À réactiver depuis le mode de récupération : csrutil enable", settingsURL: nil),
            SecurityCheck(id: "gatekeeper", title: "Gatekeeper",
                          ok: yes(gk, "enabled"), detail: "Bloque les apps non vérifiées par Apple.",
                          fixHint: "Réglages › Confidentialité et sécurité",
                          settingsURL: "x-apple.systempreferences:com.apple.preference.security?General"),
            SecurityCheck(id: "filevault", title: "FileVault (chiffrement du disque)",
                          ok: yes(fv, "is on"), detail: "Protège tes données si le Mac est volé.",
                          fixHint: "Réglages › Confidentialité et sécurité › FileVault",
                          settingsURL: "x-apple.systempreferences:com.apple.preference.security?FDE"),
            SecurityCheck(id: "firewall", title: "Coupe-feu",
                          ok: fw.isEmpty ? nil : (fw.contains("enabled") || fw.contains("State = 1")),
                          detail: "Filtre les connexions entrantes.",
                          fixHint: "Réglages › Réseau › Coupe-feu",
                          settingsURL: "x-apple.systempreferences:com.apple.Network-Settings.extension?Firewall"),
            SecurityCheck(id: "xprotect", title: "XProtect (antivirus intégré d'Apple)",
                          ok: xpVersion != nil, detail: xpVersion.map { "Définitions version \($0)" } ?? "Introuvable",
                          fixHint: "Laisse les mises à jour de sécurité automatiques activées", settingsURL: nil),
            SecurityCheck(id: "autoupdate", title: "Mises à jour de sécurité automatiques",
                          ok: (autoCheck ?? true) && (critical ?? true),
                          detail: "Réponses de sécurité rapides et fichiers de données système.",
                          fixHint: "Réglages › Général › Mise à jour de logiciels › Mises à jour automatiques",
                          settingsURL: "x-apple.systempreferences:com.apple.Software-Update-Settings.extension"),
            SecurityCheck(id: "timemachine", title: "Sauvegarde Time Machine",
                          ok: tmOK, detail: tmDetail,
                          fixHint: tm.configured ? "Branche ton disque de sauvegarde ou lance une sauvegarde"
                                                 : "Réglages › Général › Time Machine › Ajouter un disque de sauvegarde",
                          settingsURL: "x-apple.systempreferences:com.apple.Time-Machine-Settings.extension"),
            SecurityCheck(id: "pending", title: "macOS à jour",
                          ok: pending.isEmpty ? nil : !hasPending,
                          detail: hasPending ? "Des mises à jour macOS sont en attente." : "Aucune mise à jour connue en attente.",
                          fixHint: "Installe les mises à jour proposées",
                          settingsURL: "x-apple.systempreferences:com.apple.Software-Update-Settings.extension")
        ]
    }

    // MARK: Analyse des menaces

    func scan() async {
        guard !isScanning else { return }
        isScanning = true
        threats = []
        let depth = self.depth
        let ignored = self.ignored

        progressLabel = "État de sécurité du système…"
        await refreshChecks()

        progressLabel = "Éléments lancés automatiquement…"
        var found = await Task.detached { Self.scanLaunchItems() }.value

        progressLabel = "Profils et tâches planifiées…"
        found += await Task.detached { Self.scanProfilesAndCron() }.value

        if depth != .quick {
            progressLabel = "Extensions des navigateurs…"
            found += await Task.detached { Self.scanBrowserExtensions() }.value
            progressLabel = "Applications installées…"
            found += await Task.detached { Self.scanApps(verifySignatures: depth == .deep) }.value
        }
        if depth == .deep {
            progressLabel = "Dossiers de bibliothèque…"
            found += await Task.detached { Self.scanLibraryForKnownBad() }.value
        }

        threats = found
            .filter { !ignored.contains($0.url.path) }
            .sorted { $0.level == $1.level ? $0.title < $1.title : $0.level > $1.level }
        lastScan = Date()
        progressLabel = ""
        isScanning = false
    }

    nonisolated static func scanLaunchItems() -> [Threat] {
        var out: [Threat] = []
        for item in AppManager.scanLaunchItems() {
            let prog = item.program
            let progURL = URL(fileURLWithPath: prog)
            var reasons: [String] = []
            var level: ThreatLevel = .info
            var kind: ThreatKind = .persistence

            if let k = matchKnown(item.label + " " + prog) { reasons.append("correspond à un logiciel indésirable connu"); level = .high; kind = k }
            if prog != "—" && !FS.exists(progURL) { reasons.append("le programme ciblé n'existe plus"); level = max(level, .low) }
            let hiddenPath = progURL.pathComponents.contains { $0.hasPrefix(".") && $0 != "." }
            if hiddenPath { reasons.append("programme caché dans un dossier invisible"); level = max(level, .high) }
            if ["/tmp/", "/private/tmp/", "/Users/Shared/", "/var/tmp/"].contains(where: { prog.hasPrefix($0) }) {
                reasons.append("programme dans un dossier temporaire ou partagé"); level = max(level, .high)
            }
            if FS.exists(progURL), !prog.hasPrefix("/System/"), !prog.hasPrefix("/usr/") {
                let (sig, _) = CodeSign.status(of: progURL)
                if sig.isSuspicious { reasons.append("programme \(sig.rawValue.lowercased())"); level = max(level, .medium) }
            }
            guard !reasons.isEmpty else { continue }
            out.append(Threat(url: item.url, title: item.label,
                              detail: reasons.joined(separator: " · ").capitalizedFirst + " — " + prog,
                              kind: kind, level: level, selected: level >= .medium,
                              removable: item.isRemovable || level >= .high, launchLabel: item.label))
        }
        return out
    }

    nonisolated static func scanProfilesAndCron() -> [Threat] {
        var out: [Threat] = []
        let prof = Shell.run("/usr/bin/profiles", ["list"], timeout: 15).output
        let profiles = prof.split(separator: "\n").filter { $0.contains("profileIdentifier:") }
        for line in profiles {
            let ident = line.components(separatedBy: "profileIdentifier:").last?.trimmingCharacters(in: .whitespaces) ?? "?"
            let bad = matchKnown(ident) != nil
            out.append(Threat(url: URL(fileURLWithPath: "/"), title: ident,
                              detail: "Un profil peut imposer une page d'accueil, un proxy ou des certificats. À supprimer dans Réglages › Général › Gestion des appareils si tu ne le reconnais pas.",
                              kind: .profile, level: bad ? .high : .low, selected: false, removable: false))
        }
        let cron = Shell.run("/usr/bin/crontab", ["-l"], timeout: 10)
        if cron.status == 0 {
            for line in cron.output.split(separator: "\n") where !line.hasPrefix("#") && !line.trimmingCharacters(in: .whitespaces).isEmpty {
                let bad = matchKnown(String(line)) != nil || line.contains("curl") && line.contains("| sh")
                out.append(Threat(url: URL(fileURLWithPath: "/"), title: "Tâche cron",
                                  detail: String(line), kind: .cron, level: bad ? .high : .info,
                                  selected: false, removable: false))
            }
        }
        return out
    }

    nonisolated static func scanBrowserExtensions() -> [Threat] {
        BrowserExtensions.all().compactMap { ext in
            let bad = matchKnown(ext.name + " " + ext.identifier)
            let risky = ext.permissions.contains("<all_urls>") || ext.permissions.contains("webRequestBlocking")
                || ext.permissions.contains("proxy") || ext.permissions.contains("nativeMessaging")
            guard bad != nil || risky else { return nil }
            return Threat(url: ext.url, title: "\(ext.name) (\(ext.browser))",
                          detail: bad != nil ? "Extension publicitaire connue." :
                            "Peut lire et modifier toutes les pages visitées (\(ext.permissions.filter { ["<all_urls>", "webRequestBlocking", "proxy", "nativeMessaging"].contains($0) }.joined(separator: ", "))). Normal pour un bloqueur de pub ou un gestionnaire de mots de passe.",
                          kind: .extensionRisk, level: bad != nil ? .high : .info, selected: bad != nil)
        }
    }

    nonisolated static func scanApps(verifySignatures: Bool) -> [Threat] {
        var out: [Threat] = []
        for root in ["/Applications", "~/Applications"].map(FS.url) {
            for app in FS.children(root, hidden: false) where app.pathExtension == "app" {
                let bundle = Bundle(url: app)
                let text = app.lastPathComponent + " " + (bundle?.bundleIdentifier ?? "")
                if let k = matchKnown(text) {
                    out.append(Threat(url: app, title: app.deletingPathExtension().lastPathComponent,
                                      detail: k == .adware ? "Logiciel publicitaire connu." :
                                        "Application réputée pour ses alertes alarmistes et abonnements forcés.",
                                      kind: k, level: k == .adware ? .high : .medium, selected: true))
                    continue
                }
                if verifySignatures {
                    let (sig, _) = CodeSign.status(of: app)
                    if sig.isSuspicious {
                        out.append(Threat(url: app, title: app.deletingPathExtension().lastPathComponent,
                                          detail: "\(sig.rawValue) : macOS ne peut pas garantir sa provenance. Normal pour certains outils open source.",
                                          kind: .unsigned, level: .low, selected: false))
                    }
                }
            }
        }
        return out
    }

    nonisolated static func scanLibraryForKnownBad() -> [Threat] {
        var out: [Threat] = []
        for dir in ["~/Library/Application Support", "/Library/Application Support", "~/Library/Caches",
                    "~/Library/Preferences", "/Library/Preferences", "~/Library/Safari/Extensions"] {
            for child in FS.children(FS.url(dir)) {
                if let k = matchKnown(child.lastPathComponent) {
                    out.append(Threat(url: child, title: child.lastPathComponent,
                                      detail: "Fichiers résiduels d'un logiciel indésirable connu.",
                                      kind: k, level: .medium, selected: true))
                }
            }
        }
        return out
    }

    // MARK: Actions

    func toggle(_ id: UUID) {
        if let i = threats.firstIndex(where: { $0.id == id }) { threats[i].selected.toggle() }
    }

    func ignore(_ t: Threat) {
        ignoredRaw = (Array(ignored) + [t.url.path]).joined(separator: "\n")
        threats.removeAll { $0.id == t.id }
    }

    /// Supprime les menaces cochées : arrêt du lancement automatique puis envoi à la Corbeille.
    func removeSelected() async -> (removed: Int, failed: Int) {
        var removed = 0, failed = 0
        var needAdmin: [Threat] = []
        for t in threats where t.selected && t.removable {
            if let label = t.launchLabel {
                Shell.run("/bin/launchctl", ["bootout", "gui/\(getuid())/\(label)"], timeout: 10)
            }
            if FS.trash(t.url) { removed += 1 } else { needAdmin.append(t) }
        }
        if !needAdmin.isEmpty {
            // Éléments système (/Library/LaunchDaemons…) : un seul mot de passe pour tout
            let cmds = needAdmin.map { t -> String in
                var c = ""
                if let l = t.launchLabel { c += "/bin/launchctl bootout system/\(Shell.quote(l)) 2>/dev/null; " }
                c += "/bin/mv \(Shell.quote(t.url.path)) \(Shell.quote(FS.home.appendingPathComponent(".Trash").path + "/"))"
                return c
            }.joined(separator: "; ")
            let r = await Shell.adminAsync(cmds)
            if r.ok { removed += needAdmin.count } else { failed += needAdmin.count }
        }
        let gone = Set(threats.filter { $0.selected && $0.removable }.map(\.id))
        if failed == 0 { threats.removeAll { gone.contains($0.id) } }
        return (removed, failed)
    }
}

extension String {
    var capitalizedFirst: String {
        self.prefix(1).uppercased() + String(self.dropFirst())
    }
}
