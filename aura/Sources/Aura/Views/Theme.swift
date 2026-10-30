import SwiftUI
import AppKit

enum AuraTheme {
    static let accent = LinearGradient(colors: [Color(red: 0.55, green: 0.36, blue: 1.0),
                                                Color(red: 0.20, green: 0.80, blue: 0.95)],
                                       startPoint: .topLeading, endPoint: .bottomTrailing)
    static let danger = LinearGradient(colors: [.pink, .orange], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let good = LinearGradient(colors: [.green, .mint], startPoint: .topLeading, endPoint: .bottomTrailing)

    static func background(for module: Module) -> some View {
        let tint = module.tint
        return ZStack {
            Color(red: 0.07, green: 0.06, blue: 0.12)
            RadialGradient(colors: [tint.opacity(0.45), .clear], center: .topTrailing, startRadius: 20, endRadius: 650)
            RadialGradient(colors: [Color.purple.opacity(0.30), .clear], center: .bottomLeading, startRadius: 10, endRadius: 600)
        }
        .ignoresSafeArea()
    }

    static func scoreColor(_ score: Int) -> Color {
        score >= 80 ? .green : score >= 55 ? .yellow : .red
    }

    static func loadColor(_ ratio: Double) -> Color {
        ratio < 0.6 ? .green : ratio < 0.85 ? .orange : .red
    }
}

// MARK: - Carte « verre »

struct GlassCard<Content: View>: View {
    var padding: CGFloat = 18
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous)
                .strokeBorder(.white.opacity(0.08)))
    }
}

// MARK: - Jauge circulaire

struct RingGauge: View {
    var value: Double          // 0…1
    var label: String
    var caption: String = ""
    var color: Color = .accentColor
    var size: CGFloat = 110
    var lineWidth: CGFloat = 11

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                Circle().stroke(.white.opacity(0.08), lineWidth: lineWidth)
                Circle()
                    .trim(from: 0, to: max(0.001, min(1, value)))
                    .stroke(AngularGradient(colors: [color.opacity(0.6), color], center: .center),
                            style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .shadow(color: color.opacity(0.5), radius: 6)
                    .animation(.spring(duration: 0.8), value: value)
                VStack(spacing: 0) {
                    Text(label).font(.system(size: size * 0.2, weight: .bold, design: .rounded))
                        .contentTransition(.numericText())
                    if !caption.isEmpty {
                        Text(caption).font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
            .frame(width: size, height: size)
        }
    }
}

// MARK: - Bouton principal

struct BigButton: View {
    var title: String
    var icon: String
    var gradient: LinearGradient = AuraTheme.accent
    var busy = false
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if busy { ProgressView().controlSize(.small).tint(.white) }
                else { Image(systemName: icon) }
                Text(title).fontWeight(.semibold)
            }
            .padding(.horizontal, 26).padding(.vertical, 12)
            .background(gradient, in: Capsule())
            .foregroundStyle(.white)
            .shadow(color: .purple.opacity(0.4), radius: 12, y: 4)
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
        HStack(spacing: 14) {
            Image(systemName: module.icon)
                .font(.system(size: 26, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 52, height: 52)
                .background(LinearGradient(colors: [module.tint, module.tint.opacity(0.5)],
                                           startPoint: .topLeading, endPoint: .bottomTrailing),
                            in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(module.title).font(.system(size: 26, weight: .bold, design: .rounded))
                Text(subtitle).foregroundStyle(.secondary)
            }
            Spacer()
        }
    }
}

struct StatTile: View {
    var title: String
    var value: String
    var icon: String
    var tint: Color = .accentColor
    var body: some View {
        GlassCard(padding: 14) {
            HStack(spacing: 12) {
                Image(systemName: icon).font(.title3).foregroundStyle(tint).frame(width: 28)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.caption).foregroundStyle(.secondary)
                    Text(value).font(.system(.title3, design: .rounded).weight(.semibold))
                        .contentTransition(.numericText())
                }
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
            Image(systemName: icon).font(.system(size: 44)).foregroundStyle(AuraTheme.accent)
            Text(title).font(.title3.weight(.semibold))
            Text(message).foregroundStyle(.secondary).multilineTextAlignment(.center).frame(maxWidth: 380)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(40)
    }
}

/// Case à cocher ronde façon macOS moderne.
struct CheckCircle: View {
    var on: Bool
    var tint: Color = .accentColor
    var body: some View {
        Image(systemName: on ? "checkmark.circle.fill" : "circle")
            .font(.title3)
            .foregroundStyle(on ? tint : .secondary)
    }
}
