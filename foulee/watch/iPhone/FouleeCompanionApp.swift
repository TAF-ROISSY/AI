import SwiftUI
import WatchConnectivity

/// Petite app iPhone compagnon : reçoit une séance depuis l'appli web Foulée
/// (lien fouleewatch://plan?d=…) et la transmet à l'app de la montre.
@main
struct FouleeCompanionApp: App {
    @StateObject private var link = WatchLink()

    var body: some Scene {
        WindowGroup {
            CompanionView()
                .environmentObject(link)
                .onOpenURL { link.handle(url: $0) }
        }
    }
}

final class WatchLink: NSObject, ObservableObject, WCSessionDelegate {
    @Published var status = "En attente d’une séance envoyée depuis Foulée."
    @Published var lastName: String?
    @Published var sentAt: Date?
    private var pending: String?

    override init() {
        super.init()
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        } else {
            status = "Cet iPhone ne gère pas l’Apple Watch."
        }
    }

    /// fouleewatch://plan?d=<JSON en base64url>
    func handle(url: URL) {
        guard url.scheme == "fouleewatch",
              let comps = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let d = comps.queryItems?.first(where: { $0.name == "d" })?.value,
              let json = Self.decode(base64url: d),
              let data = json.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let name = obj["name"] as? String else {
            status = "Lien de séance illisible."
            return
        }
        lastName = name
        send(json)
    }

    private func send(_ json: String) {
        let s = WCSession.default
        guard s.activationState == .activated else {
            pending = json
            status = "Connexion à la montre…"
            return
        }
        guard s.isPaired, s.isWatchAppInstalled else {
            status = "Installe d’abord l’app Foulée sur la montre (voir README)."
            return
        }
        s.transferUserInfo(["plan": json])
        if s.isReachable {
            s.sendMessage(["plan": json], replyHandler: nil, errorHandler: nil)
        }
        try? s.updateApplicationContext(["plan": json])
        sentAt = Date()
        status = "Envoyée à la montre ✓ Ouvre Foulée sur la montre › Course guidée."
    }

    static func decode(base64url: String) -> String? {
        var b = base64url.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        while b.count % 4 != 0 { b += "=" }
        guard let data = Data(base64Encoded: b) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        DispatchQueue.main.async {
            if let p = self.pending, activationState == .activated {
                self.pending = nil
                self.send(p)
            }
        }
    }

    func sessionDidBecomeInactive(_ session: WCSession) {}

    func sessionDidDeactivate(_ session: WCSession) {
        WCSession.default.activate()
    }
}

struct CompanionView: View {
    @EnvironmentObject var link: WatchLink

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "applewatch.radiowaves.left.and.right")
                .font(.system(size: 56))
                .foregroundStyle(Color(red: 0.96, green: 0.49, blue: 0.54))
            Text("Foulée ⌚").font(.largeTitle.bold())
            if let n = link.lastName {
                Text(n).font(.title3.weight(.semibold)).multilineTextAlignment(.center)
            }
            Text(link.status).multilineTextAlignment(.center).foregroundStyle(.secondary)
            if let d = link.sentAt {
                Text(d.formatted(date: .omitted, time: .shortened)).font(.footnote).foregroundStyle(.secondary)
            }
            Spacer()
            Text("Dans Foulée : séance de course › 🎧 Guidée › ⌚ Envoyer à l’Apple Watch. Cette app sert seulement de relais vers la montre.")
                .font(.footnote).multilineTextAlignment(.center).foregroundStyle(.secondary)
        }
        .padding(28)
        .preferredColorScheme(.dark)
    }
}
