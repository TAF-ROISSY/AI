import Foundation
import AppKit

struct BrowserExtension: Identifiable, Hashable {
    let id = UUID()
    let browser: String
    let name: String
    let identifier: String
    let version: String
    let url: URL
    let permissions: [String]
}

/// Lecture des extensions Chrome, Edge, Brave et Firefox.
enum BrowserExtensions {
    static let chromium: [(String, String)] = [
        ("Chrome", "~/Library/Application Support/Google/Chrome"),
        ("Edge", "~/Library/Application Support/Microsoft Edge"),
        ("Brave", "~/Library/Application Support/BraveSoftware/Brave-Browser"),
        ("Vivaldi", "~/Library/Application Support/Vivaldi"),
        ("Opera", "~/Library/Application Support/com.operasoftware.Opera")
    ]

    static func all() -> [BrowserExtension] {
        var out: [BrowserExtension] = []
        for (browser, base) in chromium {
            let profiles = FS.children(FS.url(base)).filter {
                $0.lastPathComponent == "Default" || $0.lastPathComponent.hasPrefix("Profile")
            } + [FS.url(base)]   // Opera range ses extensions à la racine
            for profile in profiles {
                for extDir in FS.children(profile.appendingPathComponent("Extensions"), hidden: false) {
                    guard let versionDir = FS.children(extDir, hidden: false).sorted(by: { $0.path > $1.path }).first,
                          let data = try? Data(contentsOf: versionDir.appendingPathComponent("manifest.json")),
                          let m = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { continue }
                    let rawName = m["name"] as? String ?? extDir.lastPathComponent
                    let name = resolve(rawName, in: versionDir, defaultLocale: m["default_locale"] as? String)
                    // Les composants internes de Chrome n'ont pas d'intérêt ici
                    if name.isEmpty || name.hasPrefix("__MSG") { continue }
                    var perms = (m["permissions"] as? [Any])?.compactMap { $0 as? String } ?? []
                    perms += (m["host_permissions"] as? [String]) ?? []
                    out.append(BrowserExtension(browser: browser, name: name, identifier: extDir.lastPathComponent,
                                                version: m["version"] as? String ?? "", url: extDir, permissions: perms))
                }
            }
        }
        // Firefox
        for profile in FS.children(FS.url("~/Library/Application Support/Firefox/Profiles")) {
            guard let data = try? Data(contentsOf: profile.appendingPathComponent("extensions.json")),
                  let j = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let addons = j["addons"] as? [[String: Any]] else { continue }
            for a in addons where (a["location"] as? String) == "app-profile" {
                let loc = a["defaultLocale"] as? [String: Any]
                let path = a["path"] as? String ?? profile.path
                let perms = ((a["userPermissions"] as? [String: Any])?["origins"] as? [String]) ?? []
                out.append(BrowserExtension(browser: "Firefox", name: loc?["name"] as? String ?? (a["id"] as? String ?? "?"),
                                            identifier: a["id"] as? String ?? "", version: a["version"] as? String ?? "",
                                            url: URL(fileURLWithPath: path), permissions: perms))
            }
        }
        return out
    }

    /// Traduit les noms « __MSG_appName__ » grâce aux fichiers de langue de l'extension.
    private static func resolve(_ raw: String, in dir: URL, defaultLocale: String?) -> String {
        guard raw.hasPrefix("__MSG_"), raw.hasSuffix("__") else { return raw }
        let key = String(raw.dropFirst(6).dropLast(2)).lowercased()
        for loc in ["fr", defaultLocale ?? "en", "en", "en_US"] {
            let f = dir.appendingPathComponent("_locales/\(loc)/messages.json")
            guard let d = try? Data(contentsOf: f),
                  let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { continue }
            if let entry = j.first(where: { $0.key.lowercased() == key })?.value as? [String: Any],
               let msg = entry["message"] as? String { return msg }
        }
        return ""
    }
}

struct SystemExtensionItem: Identifiable, Hashable {
    let id = UUID()
    let category: ExtensionCategory
    let name: String
    let url: URL
    let detail: String
    var enabled: Bool = true
    var pluginID: String?     // pour les extensions d'apps (activables / désactivables)
    var needsAdmin: Bool { !url.path.hasPrefix(FS.home.path) && pluginID == nil }
}

enum ExtensionCategory: String, CaseIterable, Identifiable {
    case browser = "Navigateurs"
    case safari = "Safari"
    case appExtensions = "Extensions d'apps (Finder, partage…)"
    case prefPanes = "Volets de réglages"
    case spotlight = "Modules Spotlight"
    case quickLook = "Modules Coup d'œil"
    case internetPlugins = "Modules Internet"
    case screenSavers = "Économiseurs d'écran"
    case audio = "Pilotes audio"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .browser: return "globe"
        case .safari: return "safari"
        case .appExtensions: return "puzzlepiece.extension"
        case .prefPanes: return "gearshape.2"
        case .spotlight: return "magnifyingglass"
        case .quickLook: return "eye"
        case .internetPlugins: return "network"
        case .screenSavers: return "sparkles.tv"
        case .audio: return "waveform"
        }
    }
}

@MainActor
final class ExtensionManager: ObservableObject {
    @Published var browserExtensions: [BrowserExtension] = []
    @Published var items: [SystemExtensionItem] = []
    @Published var isLoading = false
    @Published var message = ""

    func load() async {
        isLoading = true
        browserExtensions = await Task.detached { BrowserExtensions.all() }.value
            .sorted { $0.browser == $1.browser ? $0.name < $1.name : $0.browser < $1.browser }
        items = await Task.detached { Self.scanSystem() }.value
        isLoading = false
    }

    nonisolated static func scanSystem() -> [SystemExtensionItem] {
        var out: [SystemExtensionItem] = []
        let folders: [(ExtensionCategory, [String], String)] = [
            (.prefPanes, ["~/Library/PreferencePanes", "/Library/PreferencePanes"], "prefPane"),
            (.spotlight, ["~/Library/Spotlight", "/Library/Spotlight"], "mdimporter"),
            (.quickLook, ["~/Library/QuickLook", "/Library/QuickLook"], "qlgenerator"),
            (.internetPlugins, ["~/Library/Internet Plug-Ins", "/Library/Internet Plug-Ins"], ""),
            (.screenSavers, ["~/Library/Screen Savers", "/Library/Screen Savers"], "saver"),
            (.audio, ["/Library/Audio/Plug-Ins/HAL"], "driver")
        ]
        for (cat, dirs, ext) in folders {
            for dir in dirs {
                for u in FS.children(FS.url(dir), hidden: false) where ext.isEmpty || u.pathExtension == ext {
                    let b = Bundle(url: u)
                    let v = b?.infoDictionary?["CFBundleShortVersionString"] as? String
                    out.append(SystemExtensionItem(category: cat, name: u.deletingPathExtension().lastPathComponent, url: u,
                                                   detail: [v.map { "v\($0)" }, dir.hasPrefix("~") ? "Utilisateur" : "Tous les utilisateurs"]
                                                       .compactMap { $0 }.joined(separator: " · ")))
                }
            }
        }
        // Extensions d'apps via pluginkit (Safari, Finder, partage, widgets…)
        let r = Shell.run("/usr/bin/pluginkit", ["-mAvvv"], timeout: 40).output
        out += parsePluginKit(r)
        return out
    }

    /// Analyse la sortie de `pluginkit -mAvvv` (blocs séparés par une ligne vide).
    nonisolated static func parsePluginKit(_ text: String) -> [SystemExtensionItem] {
        var out: [SystemExtensionItem] = []
        let blocks = text.components(separatedBy: "\n\n")
        for block in blocks {
            let lines = block.split(separator: "\n").map { String($0).trimmingCharacters(in: .whitespaces) }
            guard let first = lines.first else { continue }
            // Ligne 1 : "+    com.editeur.ext(1.0)" ; + = activé, - = désactivé
            let enabled = !first.hasPrefix("-")
            let ident = first.drop(while: { "+-=! ".contains($0) }).split(separator: "(").first.map(String.init) ?? ""
            func field(_ k: String) -> String? {
                lines.first { $0.hasPrefix(k + " = ") }.map { String($0.dropFirst(k.count + 3)) }
            }
            guard !ident.isEmpty, let path = field("Path") else { continue }
            if path.hasPrefix("/System/") || ident.hasPrefix("com.apple.") { continue }
            let sdk = field("SDK") ?? ""
            let parent = field("Parent Bundle").map { URL(fileURLWithPath: $0).deletingPathExtension().lastPathComponent }
            let name = field("Display Name") ?? URL(fileURLWithPath: path).deletingPathExtension().lastPathComponent
            out.append(SystemExtensionItem(category: sdk.contains("Safari") ? .safari : .appExtensions,
                                           name: name, url: URL(fileURLWithPath: path),
                                           detail: [parent.map { "fournie par \($0)" }, sdk].compactMap { $0 }.joined(separator: " · "),
                                           enabled: enabled, pluginID: ident))
        }
        return out
    }

    func setEnabled(_ item: SystemExtensionItem, _ on: Bool) {
        guard let pid = item.pluginID else { return }
        Shell.run("/usr/bin/pluginkit", ["-e", on ? "use" : "ignore", "-i", pid], timeout: 10)
        if let i = items.firstIndex(where: { $0.id == item.id }) { items[i].enabled = on }
        message = "\(item.name) \(on ? "activée" : "désactivée")"
    }

    func remove(_ item: SystemExtensionItem) {
        if FS.trash(item.url) {
            items.removeAll { $0.id == item.id }
            message = "\(item.name) envoyé à la Corbeille"
        } else {
            let dest = FS.home.appendingPathComponent(".Trash").path + "/"
            let r = Shell.admin("/bin/mv \(Shell.quote(item.url.path)) \(Shell.quote(dest))")
            if r.ok { items.removeAll { $0.id == item.id }; message = "\(item.name) envoyé à la Corbeille" }
            else { message = "Suppression annulée" }
        }
    }

    func remove(_ ext: BrowserExtension) {
        if FS.trash(ext.url) {
            browserExtensions.removeAll { $0.id == ext.id }
            message = "\(ext.name) retirée de \(ext.browser) (relance le navigateur)"
        } else {
            message = "Impossible de retirer \(ext.name) : ferme \(ext.browser) puis réessaie."
        }
    }

    func openBrowserExtensionsPage(_ browser: String) {
        let map = ["Chrome": ("Google Chrome", "chrome://extensions"), "Edge": ("Microsoft Edge", "edge://extensions"),
                   "Brave": ("Brave Browser", "brave://extensions"), "Vivaldi": ("Vivaldi", "vivaldi://extensions"),
                   "Opera": ("Opera", "opera://extensions"), "Firefox": ("Firefox", "about:addons")]
        guard let pair = map[browser] else { return }
        Shell.run("/usr/bin/open", ["-a", pair.0, pair.1], timeout: 10)
    }
}
