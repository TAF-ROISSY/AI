import SwiftUI
import AppKit

enum Module: String, CaseIterable, Identifiable {
    case smartScan
    case cleanup
    case security, privacy, permissions
    case monitor, activity, battery, network, disks, maintenance, launch
    case apps, updater, extensions
    case largeFiles, duplicates, similarImages, spaceMap, volumes, cloud, tidy, shredder

    var id: String { rawValue }

    var title: String {
        switch self {
        case .smartScan: "Analyse intelligente"
        case .cleanup: "Déchets système"
        case .security: "Sécurité"
        case .privacy: "Confidentialité"
        case .permissions: "Autorisations des apps"
        case .monitor: "Surveillance"
        case .activity: "Applications actives"
        case .battery: "Batterie et veille"
        case .network: "Réseau"
        case .disks: "Disques"
        case .maintenance: "Maintenance"
        case .launch: "Démarrage et arrière-plan"
        case .apps: "Désinstalleur"
        case .updater: "Mises à jour"
        case .extensions: "Extensions"
        case .largeFiles: "Gros et vieux fichiers"
        case .duplicates: "Doublons"
        case .similarImages: "Images similaires"
        case .spaceMap: "Carte de l'espace"
        case .volumes: "Supports amovibles"
        case .cloud: "Nettoyage du cloud"
        case .tidy: "Rangement"
        case .shredder: "Broyeur"
        }
    }

    var icon: String {
        switch self {
        case .smartScan: "sparkles"
        case .cleanup: "wand.and.stars"
        case .security: "shield.lefthalf.filled"
        case .privacy: "hand.raised.fill"
        case .permissions: "lock.rectangle.stack.fill"
        case .monitor: "waveform.path.ecg"
        case .activity: "rectangle.stack.fill"
        case .battery: "battery.75percent"
        case .network: "wifi"
        case .disks: "internaldrive.fill"
        case .maintenance: "wrench.and.screwdriver.fill"
        case .launch: "power.circle.fill"
        case .apps: "square.grid.2x2.fill"
        case .updater: "arrow.triangle.2.circlepath"
        case .extensions: "puzzlepiece.extension.fill"
        case .largeFiles: "doc.badge.ellipsis"
        case .duplicates: "square.on.square"
        case .similarImages: "photo.stack.fill"
        case .spaceMap: "chart.pie.fill"
        case .volumes: "externaldrive.fill"
        case .cloud: "icloud.fill"
        case .tidy: "tray.2.fill"
        case .shredder: "scissors"
        }
    }

    /// Un seul accent pour tous les modules : le jaune signalétique.
    var tint: Color { AuraTheme.signal }

    var section: String {
        switch self {
        case .smartScan, .cleanup: ""
        case .security, .privacy, .permissions: "Protection"
        case .monitor, .activity, .battery, .network, .disks, .maintenance, .launch: "Performances"
        case .apps, .updater, .extensions: "Applications"
        case .largeFiles, .duplicates, .similarImages, .spaceMap, .volumes, .cloud, .tidy, .shredder: "Fichiers"
        }
    }

    static let sections = ["", "Protection", "Performances", "Applications", "Fichiers"]
}

struct ContentView: View {
    @EnvironmentObject var router: Router
    @EnvironmentObject var volumes: VolumeManager
    @EnvironmentObject var alerts: HealthCenter
    @EnvironmentObject var selfUpdate: SelfUpdater
    @EnvironmentObject var guardian: Guardian
    @EnvironmentObject var activity: AppActivityMonitor
    @Etat private var showNotes = false
    @Etat private var hasFDA = true
    private var current: Module { router.selection ?? .smartScan }

    var body: some View {
        NavigationSplitView {
            sidebar
                .navigationSplitViewColumnWidth(min: 230, ideal: 248)
        } detail: {
            ZStack {
                AuraTheme.background(for: current)
                VStack(spacing: 0) {
                    if !hasFDA { fdaBanner }
                    if let rel = selfUpdate.available { updateBanner(rel) }
                    if let a = alerts.activeAlert { alertBanner(a) }
                    detail
                        .transition(.opacity)
                        .id(current)
                }
            }
            .animation(.easeOut(duration: 0.18), value: current)
        }
        .tint(AuraTheme.signal)
        .buttonStyle(AuraButton())
        .font(.auraBody)
        .foregroundStyle(AuraTheme.legend)
        .onAppear { hasFDA = FS.hasFullDiskAccess }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            let v = FS.hasFullDiskAccess
            if v != hasFDA { hasFDA = v }
        }
    }

    private var sidebar: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Image(systemName: "sparkle").font(.aura(15, .semibold)).foregroundStyle(AuraTheme.signal)
                Text("Aura").font(.auraDisplay(20)).foregroundStyle(AuraTheme.legend)
                Spacer()
            }
            .padding(.horizontal, 18).padding(.top, 34).padding(.bottom, 14)

            ScrollView {
                VStack(alignment: .leading, spacing: 1) {
                    ForEach(Module.sections, id: \.self) { section in
                        if !section.isEmpty {
                            Text(section)
                                .font(.aura(11.5, .semibold))
                                .foregroundStyle(AuraTheme.legendFaint)
                                .padding(.horizontal, 18).padding(.top, 16).padding(.bottom, 4)
                        }
                        ForEach(Module.allCases.filter { $0.section == section }) { row($0) }
                    }
                }
                .padding(.bottom, 12)
            }
            SidebarFooter()
        }
        .background(AuraTheme.sidebar.ignoresSafeArea())
        .overlay(alignment: .trailing) { Rectangle().fill(Color.black.opacity(0.4)).frame(width: 1).ignoresSafeArea() }
    }

    private func row(_ m: Module) -> some View {
        let selected = m == current
        return Button { router.selection = m } label: {
            HStack(spacing: 10) {
                Image(systemName: m.icon)
                    .font(.aura(13, .medium))
                    .foregroundStyle(selected ? AuraTheme.signal : AuraTheme.legendDim)
                    .frame(width: 20)
                Text(m.title)
                    .font(.aura(13.5, selected ? .semibold : .regular))
                    .foregroundStyle(selected ? AuraTheme.legend : AuraTheme.legend.opacity(0.82))
                    .lineLimit(1)
                Spacer(minLength: 4)
                badge(for: m)
            }
            .padding(.horizontal, 10).padding(.vertical, 6)
            .background {
                if selected {
                    RoundedRectangle(cornerRadius: 7, style: .continuous).fill(AuraTheme.panelRaised)
                }
            }
            .overlay(alignment: .leading) {
                if selected {
                    Capsule().fill(AuraTheme.signal).frame(width: 3, height: 16).offset(x: -6)
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 10)
    }

    @ViewBuilder
    private func badge(for m: Module) -> some View {
        if m == .activity && !activity.greedyApps.isEmpty {
            countBadge(activity.greedyApps.count, AuraTheme.amber)
        } else if m == .security && guardian.unhandledCount > 0 {
            countBadge(guardian.unhandledCount, AuraTheme.red)
        } else if m == .volumes && !volumes.externalVolumes.isEmpty {
            countBadge(volumes.externalVolumes.count, AuraTheme.legendDim)
        }
    }

    private func countBadge(_ n: Int, _ color: Color) -> some View {
        Text("\(n)")
            .font(.auraReadout(12))
            .foregroundStyle(AuraTheme.onSignal)
            .padding(.horizontal, 6).padding(.vertical, 1)
            .background(color, in: Capsule())
    }

    private var fdaBanner: some View {
        HStack(spacing: 12) {
            Image(systemName: "lock.shield.fill").foregroundStyle(AuraTheme.amber)
            VStack(alignment: .leading, spacing: 2) {
                Text("Accès complet au disque requis").fontWeight(.semibold)
                Text("Sans lui, Aura ne voit qu'une partie des fichiers (Mail, Safari, autorisations, conteneurs…).")
                    .font(.auraCaption).foregroundStyle(.secondary)
            }
            Spacer()
            Button("Ouvrir les réglages") { FS.openFullDiskAccessSettings() }
                .buttonStyle(AuraButton(.primary))
        }
        .padding(.horizontal, 28).padding(.vertical, 12)
        .background(AuraTheme.panel)
        .overlay(alignment: .bottom) { Rectangle().fill(AuraTheme.amber).frame(height: 2) }
    }

    private func updateBanner(_ rel: SelfUpdater.Release) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "arrow.down.app.fill").font(.aura(18)).foregroundStyle(AuraTheme.signal)
            VStack(alignment: .leading, spacing: 2) {
                Text("Aura \(rel.version) est disponible").fontWeight(.semibold)
                Text(selfUpdate.isInstalling ? selfUpdate.status : "Tu as la version \(selfUpdate.currentVersion).")
                    .font(.auraCaption).foregroundStyle(.secondary)
            }
            if selfUpdate.isInstalling {
                ProgressView(value: selfUpdate.progress).frame(width: 140)
            }
            Spacer()
            if !rel.notes.isEmpty {
                Button("Nouveautés") { showNotes = true }
                    .popover(isPresented: $showNotes) {
                        ScrollView {
                            Text(rel.notes).padding().frame(width: 380, alignment: .leading)
                        }
                        .frame(maxHeight: 360)
                    }
            }
            Button("Installer et redémarrer") { Task { await selfUpdate.install() } }
                .buttonStyle(AuraButton(.primary))
                .disabled(selfUpdate.isInstalling)
        }
        .padding(.horizontal, 28).padding(.vertical, 12)
        .background(AuraTheme.panel)
        .overlay(alignment: .bottom) { Rectangle().fill(AuraTheme.signal).frame(height: 2) }
    }

    private func alertBanner(_ a: HealthAlert) -> some View {
        HStack(spacing: 12) {
            Image(systemName: a.icon).foregroundStyle(a.color)
            VStack(alignment: .leading, spacing: 2) {
                Text(a.title).fontWeight(.semibold)
                Text(a.message).font(.auraCaption).foregroundStyle(.secondary)
            }
            Spacer()
            if let target = a.module {
                Button("Voir") { router.open(target) }.buttonStyle(AuraButton(.primary))
            }
            Button { alerts.dismiss() } label: { Image(systemName: "xmark") }.buttonStyle(.borderless)
                .help("Masquer cette alerte")
        }
        .padding(.horizontal, 28).padding(.vertical, 12)
        .background(AuraTheme.panel)
        .overlay(alignment: .bottom) { Rectangle().fill(a.color).frame(height: 2) }
    }

    @ViewBuilder private var detail: some View {
        switch current {
        case .smartScan: SmartScanView(goTo: { router.open($0) })
        case .cleanup: CleanupView()
        case .security: SecurityView()
        case .privacy: PrivacyView()
        case .permissions: PermissionsView()
        case .monitor: MonitorView()
        case .activity: AppActivityView()
        case .battery: BatteryView()
        case .network: NetworkView()
        case .disks: DisksView()
        case .maintenance: MaintenanceView()
        case .launch: LaunchItemsView()
        case .apps: AppsView()
        case .updater: UpdaterView()
        case .extensions: ExtensionsView()
        case .largeFiles: LargeFilesView()
        case .duplicates: DuplicatesView()
        case .similarImages: SimilarImagesView()
        case .spaceMap: SpaceMapView()
        case .volumes: VolumesView()
        case .cloud: CloudView()
        case .tidy: TidyView()
        case .shredder: ShredderView()
        }
    }
}

/// Pied de la barre latérale : seul élément de la fenêtre principale qui suit
/// la surveillance en continu, pour ne pas redessiner toute la fenêtre à chaque mesure.
struct SidebarFooter: View {
    @EnvironmentObject var cleanup: CleanupEngine
    @EnvironmentObject var monitor: SystemMonitor

    var body: some View {
        HStack(spacing: 10) {
            Annunciator(color: AuraTheme.scoreColor(monitor.healthScore), size: 9)
            VStack(alignment: .leading, spacing: 1) {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text("Santé").font(.auraCaption).foregroundStyle(AuraTheme.legendDim)
                    Text("\(monitor.healthScore)").font(.auraReadout(17)).monospacedDigit()
                    Text("/ 100").font(.auraCaption2).foregroundStyle(AuraTheme.legendFaint)
                }
                Text("\(Fmt.bytes(Int64(cleanup.totalFreed))) libérés depuis l'installation")
                    .font(.auraCaption2).foregroundStyle(AuraTheme.legendFaint)
            }
            Spacer()
        }
        .padding(.horizontal, 18).padding(.vertical, 12)
        .background(AuraTheme.well)
        .overlay(alignment: .top) { Rectangle().fill(Color.black.opacity(0.4)).frame(height: 1) }
    }
}
