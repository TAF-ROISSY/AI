import Foundation
import AppKit

struct AppInfo: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let name: String
    let bundleID: String?
    let version: String?
    let size: Int64
    let lastUsed: Date?
    var isApple: Bool { bundleID?.hasPrefix("com.apple.") ?? false }
    var icon: NSImage { NSWorkspace.shared.icon(forFile: url.path) }

    static func == (a: AppInfo, b: AppInfo) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }
}

struct Leftover: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let size: Int64
    var selected = true
    var kind: String
}

struct LaunchItem: Identifiable, Hashable {
    let id = UUID()
    let url: URL
    let label: String
    let program: String
    let scope: Scope
    let runAtLoad: Bool
    var disabled = false
    enum Scope: String { case user = "Utilisateur", global = "Tous les utilisateurs", daemon = "Démon système" }
    var isRemovable: Bool { scope == .user }
}

@MainActor
final class AppManager: ObservableObject {
    @Published var apps: [AppInfo] = []
    @Published var launchItems: [LaunchItem] = []
    @Published var isLoading = false
    @Published var leftovers: [Leftover] = []
    @Published var orphans: [Leftover] = []
    @Published var isSearchingLeftovers = false
    @Published var loginItems: [String] = []
    @Published var message = ""

    // MARK: Inventaire des applications

    func load() async {
        isLoading = true
        let result = await Task.detached(priority: .userInitiated) { Self.scanApps() }.value
        apps = result.sorted { $0.size > $1.size }
        launchItems = await Task.detached { Self.scanLaunchItems() }.value
        isLoading = false
    }

    nonisolated static func scanApps() -> [AppInfo] {
        let roots = ["/Applications", "~/Applications", "/Applications/Utilities"].map(FS.url)
        var seen = Set<String>()
        var out: [AppInfo] = []
        for root in roots {
            for url in FS.children(root, hidden: false) where url.pathExtension == "app" {
                guard seen.insert(url.path).inserted else { continue }
                let bundle = Bundle(url: url)
                let info = bundle?.infoDictionary
                let name = (info?["CFBundleDisplayName"] as? String)
                    ?? (info?["CFBundleName"] as? String)
                    ?? url.deletingPathExtension().lastPathComponent
                let lastUsed = NSMetadataItem(url: url)?.value(forAttribute: "kMDItemLastUsedDate") as? Date
                out.append(AppInfo(url: url, name: name, bundleID: bundle?.bundleIdentifier,
                                   version: info?["CFBundleShortVersionString"] as? String,
                                   size: FS.size(of: url), lastUsed: lastUsed))
            }
        }
        return out
    }

    // MARK: Restes d'applications

    private nonisolated static let libraryDirs: [(String, String)] = [
        ("~/Library/Application Support", "Données d'application"),
        ("~/Library/Caches", "Caches"),
        ("~/Library/Preferences", "Préférences"),
        ("~/Library/Containers", "Conteneur"),
        ("~/Library/Group Containers", "Conteneur partagé"),
        ("~/Library/Saved Application State", "État enregistré"),
        ("~/Library/Logs", "Journaux"),
        ("~/Library/HTTPStorages", "Stockage web"),
        ("~/Library/WebKit", "Données WebKit"),
        ("~/Library/Cookies", "Cookies"),
        ("~/Library/LaunchAgents", "Agent de lancement"),
        ("~/Library/Application Scripts", "Scripts")
    ]

    nonisolated static func findLeftovers(bundleID: String?, name: String) -> [Leftover] {
        var keys: [String] = []
        if let bundleID, !bundleID.isEmpty { keys.append(bundleID.lowercased()) }
        let n = name.lowercased()
        if n.count >= 4 { keys.append(n) }
        guard !keys.isEmpty else { return [] }
        var out: [Leftover] = []
        for (dir, kind) in libraryDirs {
            for child in FS.children(FS.url(dir)) {
                let c = child.lastPathComponent.lowercased()
                let stem = (c as NSString).deletingPathExtension
                let hit = keys.contains { k in
                    stem == k || c.hasPrefix(k + ".") || c.hasSuffix("." + k) || c.contains(k + ".") && k.contains(".")
                }
                if hit { out.append(Leftover(url: child, size: FS.size(of: child), kind: kind)) }
            }
        }
        return out.sorted { $0.size > $1.size }
    }

    func searchLeftovers(for app: AppInfo) async {
        isSearchingLeftovers = true
        leftovers = await Task.detached { Self.findLeftovers(bundleID: app.bundleID, name: app.name) }.value
        isSearchingLeftovers = false
    }

    /// Désinstalle l'app et ses restes sélectionnés (vers la Corbeille).
    func uninstall(_ app: AppInfo) async -> (ok: Bool, freed: Int64) {
        if let running = NSRunningApplication.runningApplications(withBundleIdentifier: app.bundleID ?? "").first {
            running.terminate()
            try? await Task.sleep(nanoseconds: 800_000_000)
        }
        let selected = leftovers.filter(\.selected)
        let (ok, freed): (Bool, Int64) = await Task.detached {
            var freed: Int64 = 0
            let ok = FS.trash(app.url)
            if ok { freed += app.size }
            for l in selected where FS.trash(l.url) { freed += l.size }
            return (ok, freed)
        }.value
        if ok { apps.removeAll { $0.id == app.id } }
        leftovers = []
        return (ok, freed)
    }

    /// Restes orphelins : dossiers de bibliothèque dont l'app n'est plus installée.
    func findOrphans() async {
        isSearchingLeftovers = true
        let installed = Set(apps.compactMap { $0.bundleID?.lowercased() })
        orphans = await Task.detached {
            var out: [Leftover] = []
            let dirs = [("~/Library/Application Support", "Données d'application"),
                        ("~/Library/Containers", "Conteneur"),
                        ("~/Library/Saved Application State", "État enregistré"),
                        ("~/Library/Preferences", "Préférences")]
            for (dir, kind) in dirs {
                for child in FS.children(FS.url(dir)) {
                    var stem = child.lastPathComponent.lowercased()
                    for ext in [".plist", ".savedstate"] where stem.hasSuffix(ext) { stem.removeLast(ext.count) }
                    // On ne retient que les identifiants de type com.editeur.app
                    let parts = stem.split(separator: ".")
                    guard parts.count >= 3, !stem.hasPrefix("com.apple."), !stem.hasPrefix("group."),
                          !installed.contains(stem),
                          NSWorkspace.shared.urlForApplication(withBundleIdentifier: stem) == nil else { continue }
                    let size = FS.size(of: child)
                    if size > 0 { out.append(Leftover(url: child, size: size, selected: false, kind: kind)) }
                }
            }
            return out.sorted { $0.size > $1.size }
        }.value
        isSearchingLeftovers = false
    }

    func removeOrphans() async -> Int64 {
        let sel = orphans.filter(\.selected)
        let freed = await Task.detached { sel.reduce(Int64(0)) { FS.trash($1.url) ? $0 + $1.size : $0 } }.value
        orphans.removeAll(where: \.selected)
        return freed
    }

    // MARK: Agents et démons de lancement

    nonisolated static func scanLaunchItems() -> [LaunchItem] {
        let dirs: [(String, LaunchItem.Scope)] = [
            ("~/Library/LaunchAgents", .user),
            ("/Library/LaunchAgents", .global),
            ("/Library/LaunchDaemons", .daemon)
        ]
        var out: [LaunchItem] = []
        for (dir, scope) in dirs {
            for url in FS.children(FS.url(dir)) where url.pathExtension == "plist" {
                let dict = NSDictionary(contentsOf: url) as? [String: Any] ?? [:]
                let label = dict["Label"] as? String ?? url.deletingPathExtension().lastPathComponent
                let program = (dict["Program"] as? String)
                    ?? (dict["ProgramArguments"] as? [String])?.first ?? "—"
                out.append(LaunchItem(url: url, label: label, program: program, scope: scope,
                                      runAtLoad: dict["RunAtLoad"] as? Bool ?? false))
            }
        }
        // États « désactivé » enregistrés par launchctl
        let disabledOut = Shell.run("/bin/launchctl", ["print-disabled", "gui/\(getuid())"], timeout: 10).output
        let disabled = Set(disabledOut.split(separator: "\n").compactMap { line -> String? in
            guard line.contains("=> disabled") || line.contains("=> true") else { return nil }
            return line.split(separator: "\"").dropFirst().first.map(String.init)
        })
        for i in out.indices where out[i].scope == .user && disabled.contains(out[i].label) { out[i].disabled = true }
        return out.sorted { $0.label.lowercased() < $1.label.lowercased() }
    }

    /// Désactive (sans supprimer) un agent utilisateur ; réversible.
    func setLaunchItem(_ item: LaunchItem, enabled: Bool) {
        let target = "gui/\(getuid())/\(item.label)"
        if enabled {
            Shell.run("/bin/launchctl", ["enable", target], timeout: 10)
            Shell.run("/bin/launchctl", ["bootstrap", "gui/\(getuid())", item.url.path], timeout: 10)
        } else {
            Shell.run("/bin/launchctl", ["disable", target], timeout: 10)
            Shell.run("/bin/launchctl", ["bootout", target], timeout: 10)
        }
        if let i = launchItems.firstIndex(where: { $0.id == item.id }) { launchItems[i].disabled = !enabled }
    }

    // MARK: Éléments d'ouverture (apps lancées à la connexion)

    func loadLoginItems() async {
        loginItems = await Task.detached {
            let r = Shell.run("/usr/bin/osascript", ["-e", "tell application \"System Events\" to get the name of every login item"], timeout: 20)
            guard r.status == 0 else { return [String]() }
            return r.output.trimmingCharacters(in: .whitespacesAndNewlines)
                .components(separatedBy: ", ").filter { !$0.isEmpty }
        }.value
    }

    func removeLoginItem(_ name: String) async {
        let clean = name.replacingOccurrences(of: "\"", with: "")
        let script = "tell application \"System Events\" to delete login item \"\(clean)\""
        let r = await Task.detached { Shell.run("/usr/bin/osascript", ["-e", script], timeout: 20) }.value
        message = r.status == 0 ? "\(name) ne s'ouvrira plus au démarrage" : "Autorise Aura à contrôler « System Events » dans Réglages › Automatisation"
        await loadLoginItems()
    }

    /// Réinitialise une app : supprime ses préférences et données, garde l'app.
    func reset(_ app: AppInfo) async -> Int64 {
        NSRunningApplication.runningApplications(withBundleIdentifier: app.bundleID ?? "").first?.terminate()
        let selected = leftovers.filter(\.selected)
        let freed = await Task.detached { selected.reduce(Int64(0)) { FS.trash($1.url) ? $0 + $1.size : $0 } }.value
        leftovers.removeAll(where: \.selected)
        return freed
    }

    /// Arrête et retire un agent utilisateur (le .plist part à la Corbeille).
    func removeLaunchItem(_ item: LaunchItem) {
        guard item.isRemovable else { return }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        p.arguments = ["bootout", "gui/\(getuid())", item.url.path]
        try? p.run(); p.waitUntilExit()
        if FS.trash(item.url) { launchItems.removeAll { $0.id == item.id } }
    }

    func openLoginItemsSettings() {
        if let u = URL(string: "x-apple.systempreferences:com.apple.LoginItems-Settings.extension") {
            NSWorkspace.shared.open(u)
        }
    }
}
