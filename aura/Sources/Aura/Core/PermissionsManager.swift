import Foundation
import AppKit

/// Autorisation accordée à une app (base TCC de macOS).
struct AppPermission: Identifiable, Hashable {
    let id = UUID()
    let service: PermissionService
    let client: String          // identifiant de l'app ou chemin
    let allowed: Bool
    var appName: String
    var appURL: URL?
}

enum PermissionService: String, CaseIterable, Identifiable {
    case camera = "kTCCServiceCamera"
    case microphone = "kTCCServiceMicrophone"
    case screen = "kTCCServiceScreenCapture"
    case accessibility = "kTCCServiceAccessibility"
    case fullDisk = "kTCCServiceSystemPolicyAllFiles"
    case input = "kTCCServiceListenEvent"
    case automation = "kTCCServiceAppleEvents"
    case contacts = "kTCCServiceAddressBook"
    case calendar = "kTCCServiceCalendar"
    case reminders = "kTCCServiceReminders"
    case photos = "kTCCServicePhotos"
    case desktop = "kTCCServiceSystemPolicyDesktopFolder"
    case documents = "kTCCServiceSystemPolicyDocumentsFolder"
    case downloads = "kTCCServiceSystemPolicyDownloadsFolder"
    case removable = "kTCCServiceSystemPolicyRemovableVolumes"
    case network = "kTCCServiceSystemPolicyNetworkVolumes"
    case bluetooth = "kTCCServiceBluetoothAlways"
    case speech = "kTCCServiceSpeechRecognition"
    case media = "kTCCServiceMediaLibrary"
    var id: String { rawValue }

    var title: String {
        switch self {
        case .camera: return "Caméra"
        case .microphone: return "Micro"
        case .screen: return "Enregistrement de l'écran"
        case .accessibility: return "Accessibilité (contrôle du Mac)"
        case .fullDisk: return "Accès complet au disque"
        case .input: return "Surveillance de la saisie (clavier)"
        case .automation: return "Automatisation d'autres apps"
        case .contacts: return "Contacts"
        case .calendar: return "Calendriers"
        case .reminders: return "Rappels"
        case .photos: return "Photos"
        case .desktop: return "Dossier Bureau"
        case .documents: return "Dossier Documents"
        case .downloads: return "Dossier Téléchargements"
        case .removable: return "Supports amovibles"
        case .network: return "Volumes réseau"
        case .bluetooth: return "Bluetooth"
        case .speech: return "Reconnaissance vocale"
        case .media: return "Musique et médias"
        }
    }

    var icon: String {
        switch self {
        case .camera: return "camera.fill"
        case .microphone: return "mic.fill"
        case .screen: return "rectangle.dashed.badge.record"
        case .accessibility: return "accessibility"
        case .fullDisk: return "internaldrive.fill"
        case .input: return "keyboard.fill"
        case .automation: return "gearshape.2.fill"
        case .contacts: return "person.crop.circle"
        case .calendar: return "calendar"
        case .reminders: return "checklist"
        case .photos: return "photo.on.rectangle"
        case .desktop: return "menubar.dock.rectangle"
        case .documents: return "doc.fill"
        case .downloads: return "arrow.down.circle.fill"
        case .removable: return "externaldrive.fill"
        case .network: return "network"
        case .bluetooth: return "dot.radiowaves.left.and.right"
        case .speech: return "waveform"
        case .media: return "music.note"
        }
    }

    /// Autorisations sensibles : signalées en priorité.
    var isSensitive: Bool { [.camera, .microphone, .screen, .accessibility, .fullDisk, .input].contains(self) }

    /// Nom utilisé par l'outil `tccutil reset`.
    var tccutilName: String { String(rawValue.dropFirst("kTCCService".count)) }

    var settingsAnchor: String {
        switch self {
        case .camera: return "Privacy_Camera"
        case .microphone: return "Privacy_Microphone"
        case .screen: return "Privacy_ScreenCapture"
        case .accessibility: return "Privacy_Accessibility"
        case .fullDisk: return "Privacy_AllFiles"
        case .input: return "Privacy_ListenEvent"
        case .automation: return "Privacy_Automation"
        case .contacts: return "Privacy_Contacts"
        case .calendar: return "Privacy_Calendars"
        case .reminders: return "Privacy_Reminders"
        case .photos: return "Privacy_Photos"
        case .desktop, .documents, .downloads, .removable, .network: return "Privacy_FilesAndFolders"
        case .bluetooth: return "Privacy_Bluetooth"
        case .speech: return "Privacy_SpeechRecognition"
        case .media: return "Privacy_Media"
        }
    }
}

@MainActor
final class PermissionsManager: ObservableObject {
    @Published var permissions: [AppPermission] = []
    @Published var isLoading = false
    @Published var readable = true
    @Published var message = ""

    func load() async {
        isLoading = true
        let (list, ok) = await Task.detached { Self.read() }.value
        permissions = list
        readable = ok
        isLoading = false
    }

    nonisolated static func read() -> ([AppPermission], Bool) {
        let dbs = [FS.url("~/Library/Application Support/com.apple.TCC/TCC.db"),
                   URL(fileURLWithPath: "/Library/Application Support/com.apple.TCC/TCC.db")]
        var out: [AppPermission] = []
        var anyReadable = false
        for db in dbs {
            let rows = Shell.sqlite(db, "SELECT service, client, auth_value FROM access;")
            if !rows.isEmpty { anyReadable = true }
            for r in rows where r.count >= 3 {
                guard let service = PermissionService(rawValue: r[0]) else { continue }
                let client = r[1]
                let allowed = (Int(r[2]) ?? 0) >= 2
                var url: URL?
                var name = client
                if client.hasPrefix("/") {
                    url = URL(fileURLWithPath: client)
                    name = url!.lastPathComponent
                } else if let u = NSWorkspace.shared.urlForApplication(withBundleIdentifier: client) {
                    url = u
                    name = (Bundle(url: u)?.infoDictionary?["CFBundleDisplayName"] as? String)
                        ?? u.deletingPathExtension().lastPathComponent
                }
                // Les composants internes d'Apple n'apportent rien à l'utilisateur
                if client.hasPrefix("com.apple.") && url == nil { continue }
                out.append(AppPermission(service: service, client: client, allowed: allowed, appName: name, appURL: url))
            }
        }
        // Une même autorisation peut figurer dans les deux bases : on dédoublonne
        var seen = Set<String>()
        out = out.filter { seen.insert($0.service.rawValue + "|" + $0.client).inserted }
        return (out.sorted { $0.appName.lowercased() < $1.appName.lowercased() }, anyReadable)
    }

    func apps(for service: PermissionService) -> [AppPermission] {
        permissions.filter { $0.service == service }
    }

    /// Retire l'autorisation : l'app devra la redemander à sa prochaine utilisation.
    func revoke(_ p: AppPermission) async {
        let r = await Task.detached { Shell.run("/usr/bin/tccutil", ["reset", p.service.tccutilName, p.client], timeout: 10) }.value
        if r.status == 0 {
            permissions.removeAll { $0.id == p.id }
            message = "Autorisation « \(p.service.title) » retirée à \(p.appName)"
        } else {
            message = "macOS refuse : retire-la depuis les Réglages (bouton à droite)."
        }
    }

    func openSettings(_ s: PermissionService) {
        if let u = URL(string: "x-apple.systempreferences:com.apple.preference.security?\(s.settingsAnchor)") {
            NSWorkspace.shared.open(u)
        }
    }
}
