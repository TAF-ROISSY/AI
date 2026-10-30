import Foundation

/// Réglage enregistré dans UserDefaults, sans lien avec l'affichage SwiftUI.
/// (`@AppStorage` dans les objets de données provoquait des boucles de rafraîchissement.)
@propertyWrapper
struct Pref<Value> {
    let key: String
    let defaultValue: Value

    init(wrappedValue: Value, _ key: String) {
        self.key = key
        self.defaultValue = wrappedValue
    }

    var wrappedValue: Value {
        get { UserDefaults.standard.object(forKey: key) as? Value ?? defaultValue }
        nonmutating set { UserDefaults.standard.set(newValue, forKey: key) }
    }
}
