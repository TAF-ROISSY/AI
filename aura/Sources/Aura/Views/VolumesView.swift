import SwiftUI
import AppKit

struct VolumesView: View {
    @EnvironmentObject var volumes: VolumeManager
    @EnvironmentObject var router: Router
    @AppStorage("aura.autoScanVolumes") private var autoScan = true
    @Etat private var showInternal = false
    @Etat private var confirmClean: VolumeInfo? = nil
    @Etat private var confirmEject: VolumeInfo? = nil
    @Etat private var dsBlocked = VolumeManager.dsStoreBlocked

    private var shown: [VolumeInfo] {
        showInternal ? volumes.volumes : volumes.externalVolumes
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .volumes, subtitle: "Clés USB, disques externes et cartes SD : analyse, nettoyage, éjection.")

                if let v = volumes.lastMounted, volumes.volumes.contains(v) { newDriveBanner(v) }

                HStack(spacing: 16) {
                    Toggle("Analyser automatiquement chaque nouveau support", isOn: $autoScan)
                    Toggle("Afficher aussi les disques internes", isOn: $showInternal)
                    Spacer()
                    if !volumes.message.isEmpty {
                        Text(volumes.message).font(.auraCallout).foregroundStyle(AuraTheme.green).lineLimit(2)
                    }
                    Button { volumes.refresh() } label: { Label("Actualiser", systemImage: "arrow.clockwise") }
                }
                .toggleStyle(.switch).controlSize(.small)

                if shown.isEmpty {
                    GlassCard {
                        EmptyState(icon: "externaldrive.badge.questionmark", title: "Aucun support branché",
                                   message: "Branche une clé USB, un disque externe ou une carte SD : Aura le détectera tout seul.")
                    }
                } else {
                    ForEach(shown) { v in volumeCard(v) }
                }

                preventionCard
            }
            .padding(28)
        }
        .confirmationDialog("Supprimer \(Fmt.bytes(confirmClean.map { volumes.junkSize($0, selectedOnly: true) } ?? 0)) de fichiers parasites ?",
                            isPresented: Binding(get: { confirmClean != nil }, set: { if !$0 { confirmClean = nil } })) {
            Button("Supprimer définitivement", role: .destructive) {
                if let v = confirmClean { Task { await volumes.cleanJunk(v) } }
            }
        } message: {
            Text("Sur un support externe la Corbeille ne libère pas d'espace : la suppression est définitive. Tes documents ne sont jamais concernés.")
        }
        .confirmationDialog("Éjecter \(confirmEject?.name ?? "") ?",
                            isPresented: Binding(get: { confirmEject != nil }, set: { if !$0 { confirmEject = nil } })) {
            Button("Éjecter") { if let v = confirmEject { volumes.eject(v) } }
        }
    }

    // MARK: Bandeau « nouveau support »

    private func newDriveBanner(_ v: VolumeInfo) -> some View {
        GlassCard(padding: 14) {
            HStack(spacing: 12) {
                Image(systemName: "bolt.horizontal.circle.fill").font(.auraTitle2).foregroundStyle(AuraTheme.legendDim)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Nouveau support détecté : \(v.name)").fontWeight(.semibold)
                    Text(volumes.scanning.contains(v.id) ? "Analyse en cours…"
                         : "\(Fmt.bytes(volumes.junkSize(v))) de fichiers parasites · \(Fmt.bytes(v.free)) libres")
                        .font(.auraCaption).foregroundStyle(.secondary)
                }
                Spacer()
                Button("OK") { volumes.lastMounted = nil }.buttonStyle(.borderless)
            }
        }
    }

    // MARK: Carte d'un volume

    private func volumeCard(_ v: VolumeInfo) -> some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 14) {
                    Image(nsImage: v.icon).resizable().frame(width: 52, height: 52)
                    VStack(alignment: .leading, spacing: 3) {
                        HStack(spacing: 8) {
                            Text(v.name).font(.auraTitle3.bold())
                            tag(v.kindLabel, AuraTheme.cool)
                            tag(v.format, AuraTheme.legendDim)
                            if v.isReadOnly { tag("Lecture seule", AuraTheme.amber) }
                            if volumes.isProtected(v) { tag("Protégé", AuraTheme.green) }
                        }
                        Text("\(Fmt.bytes(v.used)) utilisés sur \(Fmt.bytes(v.total)) · \(Fmt.bytes(v.free)) libres")
                            .font(.auraCallout).foregroundStyle(.secondary)
                    }
                    Spacer()
                    RingGauge(value: v.usedRatio, label: Fmt.percent(v.usedRatio),
                              color: AuraTheme.loadColor(v.usedRatio), size: 64, lineWidth: 7)
                }

                // Barre d'occupation
                GeometryReader { g in
                    ZStack(alignment: .leading) {
                        Capsule().fill(.white.opacity(0.08))
                        Capsule().fill(AuraTheme.loadColor(v.usedRatio).gradient)
                            .frame(width: g.size.width * v.usedRatio)
                    }
                }
                .frame(height: 6)

                junkSection(v)

                HStack(spacing: 10) {
                    Button { NSWorkspace.shared.open(v.url) } label: { Label("Ouvrir", systemImage: "folder") }
                    Button { router.open(.voyages, roots: [v.url]) } label: { Label("Classer les photos", systemImage: "airplane.departure") }
                    Button { router.open(.duplicates, roots: [v.url]) } label: { Label("Doublons", systemImage: "square.on.square") }
                    Button { router.open(.largeFiles, roots: [v.url]) } label: { Label("Gros fichiers", systemImage: "doc.badge.ellipsis") }
                    Button { router.open(.spaceMap, roots: [v.url]) } label: { Label("Carte", systemImage: "chart.pie") }
                    Spacer()
                    if !v.isInternal && !v.isReadOnly && !volumes.isProtected(v) {
                        Button("Protéger ce support") { volumes.protect(v) }
                            .help("Empêche Spotlight et macOS d'y écrire leurs fichiers cachés")
                    }
                    if v.isEjectable || v.isRemovable || v.isNetwork {
                        Button { confirmEject = v } label: { Label("Éjecter", systemImage: "eject.fill") }
                            .buttonStyle(AuraButton(.primary))
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func junkSection(_ v: VolumeInfo) -> some View {
        let list = volumes.junk[v.id]
        if volumes.scanning.contains(v.id) {
            HStack { ProgressView().controlSize(.small); Text("Recherche des fichiers parasites…").foregroundStyle(.secondary) }
        } else if let list {
            if list.isEmpty {
                Label("Aucun fichier parasite, support impeccable.", systemImage: "checkmark.seal.fill").foregroundStyle(AuraTheme.green)
            } else {
                VStack(spacing: 6) {
                    ForEach(JunkKind.allCases.filter { k in list.contains { $0.kind == k } }) { kind in
                        let items = list.filter { $0.kind == kind }
                        let on = items.allSatisfy(\.selected)
                        Button { volumes.toggle(volume: v, kind: kind) } label: {
                            HStack(spacing: 10) {
                                CheckCircle(on: on, tint: AuraTheme.cool)
                                Image(systemName: kind.icon).frame(width: 20).foregroundStyle(.secondary)
                                Text(kind.rawValue)
                                Spacer()
                                Text("\(items.count) · \(Fmt.bytes(items.reduce(Int64(0)) { $0 + $1.size }))")
                                    .font(.auraCaption.monospacedDigit()).foregroundStyle(.secondary)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                    HStack {
                        if v.isForeignFormat && list.contains(where: { $0.kind == .appleDouble }) {
                            Button("Fusionner les « ._ » (dot_clean)") { Task { await volumes.dotClean(v) } }
                                .help("Outil Apple : réintègre les métadonnées avant de supprimer les fichiers « ._ »")
                        }
                        Spacer()
                        Button("Analyser à nouveau") { Task { await volumes.scanJunk(v) } }
                        Button("Nettoyer \(Fmt.bytes(volumes.junkSize(v, selectedOnly: true)))") { confirmClean = v }
                            .buttonStyle(AuraButton(.primary))
                            .disabled(volumes.junkSize(v, selectedOnly: true) == 0 || v.isReadOnly)
                    }
                }
                .padding(12)
                .background(.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 12))
            }
        } else {
            Button { Task { await volumes.scanJunk(v) } } label: {
                Label("Chercher les fichiers parasites", systemImage: "sparkle.magnifyingglass")
            }
        }
    }

    private func tag(_ text: String, _ color: Color) -> some View {
        Text(text).font(.auraCaption2.weight(.medium))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(color.opacity(0.2), in: Capsule())
    }

    // MARK: Prévention

    private var preventionCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 8) {
                Text("Prévention").fontWeight(.semibold)
                Toggle(isOn: Binding(get: { dsBlocked }, set: { dsBlocked = $0; volumes.setDSStoreBlocked($0) })) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Ne plus créer de .DS_Store sur les clés USB et partages réseau")
                        Text("Réglage officiel macOS. Utile pour les clés lues par une TV, un autoradio ou un PC.")
                            .font(.auraCaption).foregroundStyle(.secondary)
                    }
                }
                .toggleStyle(.switch)
            }
        }
    }
}
