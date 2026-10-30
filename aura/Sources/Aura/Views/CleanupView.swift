import SwiftUI
import AppKit

struct CleanupView: View {
    @EnvironmentObject var cleanup: CleanupEngine
    @Etat private var expanded: Set<String> = []
    @Etat private var showConfirm = false

    var body: some View {
        VStack(spacing: 18) {
            ModuleHeader(module: .cleanup, subtitle: "Détail de chaque catégorie, élément par élément.")

            HStack {
                if cleanup.isScanning || cleanup.isCleaning {
                    ProgressView(value: cleanup.progress).frame(width: 220)
                    Text(cleanup.progressLabel).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                } else if let d = cleanup.lastScanDate {
                    Text("Dernière analyse \(Fmt.relativeDate(d))").foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    Task { await cleanup.scan() }
                } label: { Label("Analyser", systemImage: "arrow.clockwise") }
                    .disabled(cleanup.isScanning || cleanup.isCleaning)
                BigButton(title: "Nettoyer \(Fmt.bytes(cleanup.totalSelected))", icon: "wand.and.stars",
                          gradient: AuraTheme.good, busy: cleanup.isCleaning) { showConfirm = true }
                    .disabled(cleanup.totalSelected == 0 || cleanup.isScanning)
            }

            if cleanup.categories.isEmpty && !cleanup.isScanning {
                EmptyState(icon: "wand.and.stars", title: "Aucune analyse pour l'instant",
                           message: "Lance une analyse pour voir précisément ce qui encombre ton Mac.")
            } else {
                ScrollView {
                    LazyVStack(spacing: 10) {
                        ForEach(cleanup.categories) { cat in categoryCard(cat) }
                    }
                }
            }
        }
        .padding(28)
        .confirmationDialog("Nettoyer \(Fmt.bytes(cleanup.totalSelected)) ?", isPresented: $showConfirm) {
            Button("Nettoyer", role: .destructive) { Task { await cleanup.clean() } }
        } message: {
            Text("Caches, journaux et Corbeille : suppression définitive. Mail, sauvegardes iOS et téléchargements : envoi à la Corbeille.")
        }
    }

    private func categoryCard(_ cat: CleanCategory) -> some View {
        GlassCard(padding: 0) {
            VStack(spacing: 0) {
                HStack(spacing: 14) {
                    Button { cleanup.toggleCategory(cat.id) } label: { CheckCircle(on: cat.isSelected, tint: cat.tint) }
                        .buttonStyle(.plain).disabled(cat.items.isEmpty)
                    Image(systemName: cat.icon).font(.title2).foregroundStyle(cat.tint).frame(width: 30)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text(cat.name).fontWeight(.semibold)
                            if cat.mode == .permanent {
                                Text("définitif").font(.caption2).padding(.horizontal, 5).padding(.vertical, 1)
                                    .background(.red.opacity(0.2), in: Capsule())
                            }
                        }
                        Text(cat.detail).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(Fmt.bytes(cat.totalSize)).font(.system(.body, design: .rounded).weight(.semibold))
                        Text("\(cat.items.count) éléments").font(.caption2).foregroundStyle(.secondary)
                    }
                    Button {
                        withAnimation { if expanded.contains(cat.id) { expanded.remove(cat.id) } else { expanded.insert(cat.id) } }
                    } label: {
                        Image(systemName: "chevron.down")
                            .rotationEffect(.degrees(expanded.contains(cat.id) ? 180 : 0))
                    }
                    .buttonStyle(.plain).disabled(cat.items.isEmpty)
                }
                .padding(16)

                if expanded.contains(cat.id) {
                    Divider().opacity(0.3)
                    VStack(spacing: 0) {
                        ForEach(cat.items.prefix(300)) { item in
                            HStack(spacing: 10) {
                                Button { cleanup.toggleItem(category: cat.id, item: item.id) } label: {
                                    CheckCircle(on: item.selected, tint: cat.tint).font(.body)
                                }.buttonStyle(.plain)
                                Text(item.name).lineLimit(1).truncationMode(.middle)
                                Spacer()
                                Text(Fmt.bytes(item.size)).font(.caption).foregroundStyle(.secondary)
                                Button { FS.reveal(item.url) } label: { Image(systemName: "magnifyingglass") }
                                    .buttonStyle(.borderless).help("Afficher dans le Finder")
                            }
                            .padding(.horizontal, 20).padding(.vertical, 6)
                        }
                        if cat.items.count > 300 {
                            Text("+ \(cat.items.count - 300) autres éléments").font(.caption).foregroundStyle(.secondary).padding(8)
                        }
                    }
                    .padding(.vertical, 6)
                }
            }
        }
    }
}
