import SwiftUI

/// Équivalent de `@State` sans macro.
/// Les outils Apple récents déclarent `@State` comme une macro dont le module
/// (SwiftUIMacros) n'est livré qu'avec Xcode complet : ce wrapper stocke un
/// `State` classique, ce qui compile avec les simples outils en ligne de commande.
@propertyWrapper
struct Etat<Value>: DynamicProperty {
    private var storage: State<Value>

    init(wrappedValue: Value) {
        storage = State(initialValue: wrappedValue)
    }

    var wrappedValue: Value {
        get { storage.wrappedValue }
        nonmutating set { storage.wrappedValue = newValue }
    }

    var projectedValue: Binding<Value> { storage.projectedValue }
}
