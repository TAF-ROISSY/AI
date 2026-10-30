import Foundation

/// Navigation partagée : permet à un module d'en ouvrir un autre sur un dossier précis
/// (ex. « Chercher les doublons sur cette clé USB »).
@MainActor
final class Router: ObservableObject {
    @Published var selection: Module? = .smartScan
    @Published var requestedRoots: [URL] = []

    func open(_ module: Module, roots: [URL] = []) {
        requestedRoots = roots
        selection = module
    }

    /// Récupère (une seule fois) les dossiers demandés par un autre module.
    func consumeRoots() -> [URL] {
        defer { requestedRoots = [] }
        return requestedRoots
    }
}
