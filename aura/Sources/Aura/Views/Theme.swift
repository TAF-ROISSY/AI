import SwiftUI
import AppKit

// MARK: - Identité « tableau de bord de vol »
//
// Panneau d'instruments gris-bleu, puits sombres pour les cadrans, légendes blanches.
// Un seul accent : le jaune de la signalétique de Roissy-CDG, réservé aux actions et à la sélection.
// Vert, ambre et rouge ne servent qu'à dire un état (comme les voyants d'un cockpit).
// Typographie : Avenir Next (Adrian Frutiger, auteur de la signalétique de CDG) ;
// chiffres de mesure en Avenir Next Condensed.

enum AuraTheme {
    // Surfaces
    static let fuselage = Color(hex: 0x1C2128)        // fond de fenêtre
    static let panel = Color(hex: 0x262D36)           // panneaux
    static let panelRaised = Color(hex: 0x313945)     // boutons, survol, sélection
    static let well = Color(hex: 0x14181D)            // puits des instruments
    static let hairline = Color(hex: 0x3A4350)        // filets
    static let sidebar = Color(hex: 0x181C22)

    // Légendes
    static let legend = Color(hex: 0xEDF1F5)
    static let legendDim = Color(hex: 0x9AA6B4)
    static let legendFaint = Color(hex: 0x66717E)

    // Signal et voyants
    static let signal = Color(hex: 0xFFCB2E)          // jaune signalétique CDG
    static let onSignal = Color(hex: 0x1A1D21)
    static let green = Color(hex: 0x4ADE80)
    static let amber = Color(hex: 0xFFAA2B)
    static let red = Color(hex: 0xFF5A4F)

    // Séries de données (graphiques, réseau entrant/sortant)
    static let cool = Color(hex: 0x6CB4FF)

    /// Teintes catégorielles sourdes pour la carte de l'espace (lisibles avec un texte blanc).
    static let categorical: [Color] = [0x3E6A8A, 0x5B5F8F, 0x2F7A6E, 0x8A6A3E, 0x7A4E6B, 0x4F7A3E,
                                       0x3E5F7A, 0x7A5A4E, 0x5A7A8A, 0x6B6B4E].map { Color(hex: $0) }

    // Compatibilité avec les écrans existants (aplats, plus de dégradés décoratifs)
    static let accent = LinearGradient(colors: [signal, signal], startPoint: .top, endPoint: .bottom)
    static let good = LinearGradient(colors: [green, green], startPoint: .top, endPoint: .bottom)
    static let danger = LinearGradient(colors: [red, red], startPoint: .top, endPoint: .bottom)

    static func background(for module: Module) -> some View {
        fuselage.ignoresSafeArea()
    }

    static func scoreColor(_ score: Int) -> Color {
        score >= 80 ? green : score >= 55 ? amber : red
    }

    static func loadColor(_ ratio: Double) -> Color {
        ratio < 0.6 ? green : ratio < 0.85 ? amber : red
    }
}

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255,
                  opacity: opacity)
    }
}

extension View {
    /// Habillage commun à toutes les fenêtres d'Aura.
    func auraChrome() -> some View {
        self.tint(AuraTheme.signal)
            .buttonStyle(AuraButton())
            .font(.auraBody)
            .foregroundStyle(AuraTheme.legend)
    }
}

// MARK: - Typographie

extension Font {
    static let auraFamily = "Avenir Next"
    static let auraCondensed = "Avenir Next Condensed"

    static func aura(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .custom(auraFamily, size: size).weight(weight)
    }
    /// Titres d'écran.
    static func auraDisplay(_ size: CGFloat) -> Font { .custom(auraFamily, size: size).weight(.semibold) }
    /// Chiffres de mesure (instruments).
    static func auraReadout(_ size: CGFloat) -> Font { .custom(auraCondensed, size: size).weight(.semibold) }

    // Échelle (rapport ~1,2) remplaçant les styles système
    static let auraLargeTitle = aura(28, .semibold)
    static let auraTitle = aura(24, .semibold)
    static let auraTitle2 = aura(20, .semibold)
    static let auraTitle3 = aura(16.5, .medium)
    static let auraHeadline = aura(14, .semibold)
    static let auraSubheadline = aura(12.5)
    static let auraBody = aura(13.5)
    static let auraCallout = aura(13)
    static let auraFootnote = aura(11.5)
    static let auraCaption = aura(11.5)
    static let auraCaption2 = aura(10.5, .medium)
}

// MARK: - Panneaux

enum PanelStyle { case panel, well }

struct GlassCard<Content: View>: View {
    var padding: CGFloat = 18
    var style: PanelStyle = .panel
    @ViewBuilder var content: Content

    var body: some View {
        let radius: CGFloat = style == .well ? 14 : 10
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(style == .well ? AuraTheme.well : AuraTheme.panel)
            }
            .overlay {
                // Panneau : arête claire en haut (tôle éclairée) ; puits : bord sombre (cavité)
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(style == .well
                                  ? AnyShapeStyle(Color.black.opacity(0.45))
                                  : AnyShapeStyle(LinearGradient(colors: [Color.white.opacity(0.09), Color.white.opacity(0.02)],
                                                                 startPoint: .top, endPoint: .bottom)),
                                  lineWidth: 1)
            }
    }
}

// MARK: - Cadran d'instrument

/// Cadran à 270° (ouvert en bas) avec graduations, comme un instrument de bord.
struct RingGauge: View {
    var value: Double          // 0…1
    var label: String
    var caption: String = ""
    var color: Color = AuraTheme.signal
    var size: CGFloat = 110
    var lineWidth: CGFloat = 11

    var body: some View {
        let v = max(0, min(1, value))
        let stroke = max(3.5, lineWidth * 0.62)
        let inset = size * 0.14
        ZStack {
            ForEach(0..<11, id: \.self) { i in
                let major = i % 5 == 0
                Capsule()
                    .fill(AuraTheme.legend.opacity(major ? 0.55 : 0.2))
                    .frame(width: major ? 2 : 1.2, height: size * (major ? 0.075 : 0.045))
                    .offset(y: -size * 0.455)
                    .rotationEffect(.degrees(-135 + Double(i) * 27))
            }
            Circle()
                .trim(from: 0, to: 0.75)
                .stroke(Color.white.opacity(0.07), style: StrokeStyle(lineWidth: stroke, lineCap: .round))
                .rotationEffect(.degrees(135))
                .padding(inset)
            Circle()
                .trim(from: 0, to: max(0.002, 0.75 * v))
                .stroke(color, style: StrokeStyle(lineWidth: stroke, lineCap: .round))
                .rotationEffect(.degrees(135))
                .padding(inset)
                .animation(.easeOut(duration: 0.6), value: v)
            VStack(spacing: -2) {
                Text(label)
                    .font(.auraReadout(size * 0.25))
                    .monospacedDigit()
                    .foregroundStyle(AuraTheme.legend)
                    .contentTransition(.numericText())
                    .minimumScaleFactor(0.6)
                    .lineLimit(1)
                if !caption.isEmpty {
                    Text(caption).font(.auraCaption2).foregroundStyle(AuraTheme.legendDim).lineLimit(1)
                }
            }
            .padding(.horizontal, size * 0.18)
            .offset(y: size * 0.03)
        }
        .frame(width: size, height: size)
    }
}

// MARK: - Boutons

enum AuraButtonKind { case primary, danger, secondary }

/// Bouton aux couleurs d'Aura : jaune signalétique (action), rouge (destruction), gris panneau (secondaire).
struct AuraButton: ButtonStyle {
    var kind: AuraButtonKind = .secondary
    init(_ kind: AuraButtonKind = .secondary) { self.kind = kind }

    func makeBody(configuration: Configuration) -> some View {
        AuraButtonBody(configuration: configuration, kind: kind)
    }
}

private struct AuraButtonBody: View {
    let configuration: ButtonStyleConfiguration
    let kind: AuraButtonKind
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.controlSize) private var controlSize

    var body: some View {
        let small = controlSize == .small || controlSize == .mini
        configuration.label
            .font(.aura(small ? 11.5 : 13, kind == .secondary ? .medium : .semibold))
            .lineLimit(1)
            .padding(.horizontal, small ? 8 : 12)
            .padding(.vertical, small ? 3 : 5.5)
            .foregroundStyle(foreground)
            .background(RoundedRectangle(cornerRadius: small ? 6 : 7, style: .continuous).fill(fill))
            .overlay {
                if kind == .secondary {
                    RoundedRectangle(cornerRadius: small ? 6 : 7, style: .continuous)
                        .strokeBorder(Color.white.opacity(0.08))
                }
            }
            .opacity(isEnabled ? (configuration.isPressed ? 0.75 : 1) : 0.4)
            .contentShape(Rectangle())
    }

    private var fill: Color {
        switch kind {
        case .primary: return AuraTheme.signal
        case .danger: return AuraTheme.red
        case .secondary: return configuration.isPressed ? AuraTheme.hairline : AuraTheme.panelRaised
        }
    }

    private var foreground: Color {
        switch kind {
        case .primary, .danger: return AuraTheme.onSignal
        case .secondary: return AuraTheme.legend
        }
    }
}

struct BigButton: View {
    var title: String
    var icon: String
    var gradient: LinearGradient = AuraTheme.accent
    var busy = false
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if busy { ProgressView().controlSize(.small).tint(AuraTheme.onSignal) }
                else { Image(systemName: icon).font(.aura(13, .semibold)) }
                Text(title).font(.aura(14, .semibold))
            }
            .padding(.horizontal, 18).padding(.vertical, 9)
            .background(RoundedRectangle(cornerRadius: 8, style: .continuous).fill(gradient))
            .foregroundStyle(AuraTheme.onSignal)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(busy)
    }
}

// MARK: - En-tête de module

struct ModuleHeader: View {
    let module: Module
    var subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Image(systemName: module.icon)
                    .font(.aura(20, .medium))
                    .foregroundStyle(AuraTheme.signal)
                Text(module.title)
                    .font(.auraDisplay(28))
                    .foregroundStyle(AuraTheme.legend)
            }
            Text(subtitle)
                .font(.auraCallout)
                .foregroundStyle(AuraTheme.legendDim)
                .frame(maxWidth: 640, alignment: .leading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Afficheurs

/// Afficheur numérique : légende discrète, chiffre en condensé.
struct StatTile: View {
    var title: String
    var value: String
    var icon: String
    var tint: Color = AuraTheme.legend

    /// Seuls les voyants (vert, ambre, rouge) colorent le chiffre.
    private var isStatus: Bool { [AuraTheme.green, AuraTheme.amber, AuraTheme.red].contains(tint) }

    var body: some View {
        GlassCard(padding: 14, style: .well) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Image(systemName: icon).font(.auraCaption).foregroundStyle(AuraTheme.legendFaint)
                    Text(title).font(.auraCaption).foregroundStyle(AuraTheme.legendDim).lineLimit(1)
                }
                Text(value)
                    .font(.auraReadout(26))
                    .monospacedDigit()
                    .foregroundStyle(isStatus ? tint : AuraTheme.legend)
                    .contentTransition(.numericText())
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
            }
        }
    }
}

struct EmptyState: View {
    var icon: String
    var title: String
    var message: String

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: icon).font(.aura(34, .light)).foregroundStyle(AuraTheme.legendFaint)
            Text(title).font(.auraTitle3).foregroundStyle(AuraTheme.legend)
            Text(message).font(.auraCallout).foregroundStyle(AuraTheme.legendDim)
                .multilineTextAlignment(.center).frame(maxWidth: 380)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(40)
    }
}

/// Case à cocher : la sélection est toujours en jaune signalétique.
struct CheckCircle: View {
    var on: Bool
    var tint: Color = AuraTheme.signal

    var body: some View {
        Image(systemName: on ? "checkmark.circle.fill" : "circle")
            .font(.aura(16))
            .foregroundStyle(on ? AuraTheme.signal : AuraTheme.legendFaint)
    }
}

/// Voyant d'état (annonciateur).
struct Annunciator: View {
    var color: Color
    var size: CGFloat = 8

    var body: some View {
        Circle()
            .fill(color)
            .frame(width: size, height: size)
            .overlay(Circle().strokeBorder(Color.black.opacity(0.35), lineWidth: 1))
            .shadow(color: color.opacity(0.6), radius: 3)
    }
}
