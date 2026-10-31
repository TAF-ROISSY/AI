import SwiftUI
import AppKit

/// Analyse intelligente : nettoyage + protection + performances + applications en un clic.
struct SmartScanView: View {
    @EnvironmentObject var cleanup: CleanupEngine
    @EnvironmentObject var monitor: SystemMonitor
    @EnvironmentObject var security: SecurityScanner
    @EnvironmentObject var maint: MaintenanceManager
    @EnvironmentObject var updater: UpdateManager
    @EnvironmentObject var apps: AppManager
    @EnvironmentObject var activity: AppActivityMonitor
    var goTo: (Module) -> Void

    @Etat private var phase: Phase = .idle
    @Etat private var step = ""
    @Etat private var pulse = false
    @Etat private var showConfirm = false
    @Etat private var doClean = true
    @Etat private var doProtect = true
    @Etat private var doSpeed = true
    @Etat private var report: [String] = []

    enum Phase { case idle, scanning, ready, running, done }

    private var threatsToRemove: Int { security.threats.filter { $0.selected && $0.removable }.count }
    private var maintCount: Int { maint.tasks.filter(\.selected).count }
    private var unusedApps: [AppInfo] {
        let limit = Date().addingTimeInterval(-180 * 86400)
        return apps.apps.filter { !$0.isApple && $0.lastUsed != nil && ($0.lastUsed ?? .distantPast) < limit }
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                ModuleHeader(module: .smartScan, subtitle: "Nettoyage, protection, vitesse et applications : tout en un seul clic.")
                hero
                HStack(spacing: 14) {
                    StatTile(title: "Processeur", value: Fmt.percent(monitor.cpuUsage), icon: "cpu", tint: AuraTheme.loadColor(monitor.cpuUsage))
                    StatTile(title: "Mémoire", value: Fmt.percent(monitor.memPressure), icon: "memorychip", tint: AuraTheme.loadColor(monitor.memPressure))
                    StatTile(title: "Espace libre", value: Fmt.bytes(monitor.diskFree), icon: "internaldrive", tint: AuraTheme.loadColor(monitor.diskUsedRatio))
                    StatTile(title: monitor.temps.cpu != nil ? "Température CPU" : "Allumé depuis",
                             value: monitor.temps.cpu.map { String(format: "%.0f °C", $0) } ?? Fmt.duration(monitor.uptime),
                             icon: monitor.temps.cpu != nil ? "thermometer.medium" : "clock")
                }
                if phase == .ready || phase == .done { pillars }
                assistant
            }
            .padding(28)
        }
        .confirmationDialog("Lancer l'entretien complet ?", isPresented: $showConfirm) {
            Button("Lancer", role: .destructive) { Task { await runAll() } }
        } message: {
            Text("Caches, journaux et Corbeille sont supprimés définitivement ; menaces et autres fichiers vont à la Corbeille. Un mot de passe peut être demandé pour la maintenance.")
        }
    }

    // MARK: Bloc central

    private var busy: Bool { phase == .scanning || phase == .running }

    private var hero: some View {
        GlassCard(padding: 28) {
            HStack(spacing: 40) {
                ZStack {
                    Circle().fill(AuraTheme.accent).frame(width: 190, height: 190)
                        .blur(radius: pulse ? 42 : 24).opacity(pulse ? 0.55 : 0.3)
                    RingGauge(value: busy ? cleanup.progress : Double(monitor.healthScore) / 100,
                              label: busy ? Fmt.percent(cleanup.progress) : "\(monitor.healthScore)",
                              caption: busy ? "en cours" : "santé",
                              color: busy ? .purple : AuraTheme.scoreColor(monitor.healthScore),
                              size: 170, lineWidth: 14)
                }
                .onAppear { withAnimation(.easeInOut(duration: 2.2).repeatForever()) { pulse = true } }

                VStack(alignment: .leading, spacing: 14) {
                    Text(headline).font(.system(size: 28, weight: .bold, design: .rounded))
                    Text(busy ? step : subline).foregroundStyle(.secondary).lineLimit(2)
                    HStack(spacing: 12) { actionButtons }
                }
                Spacer()
            }
        }
    }

    @ViewBuilder
    private var actionButtons: some View {
        switch phase {
        case .idle, .done:
            BigButton(title: "Lancer l'analyse", icon: "sparkle.magnifyingglass") { Task { await scanAll() } }
        case .scanning, .running:
            BigButton(title: phase == .scanning ? "Analyse…" : "Entretien…", icon: "sparkles", busy: true) {}
        case .ready:
            BigButton(title: "Lancer l'entretien", icon: "wand.and.stars", gradient: AuraTheme.good) { showConfirm = true }
            Button("Relancer l'analyse") { Task { await scanAll() } }.buttonStyle(.bordered)
        }
    }

    private var headline: String {
        switch phase {
        case .idle: return "Prêt à faire briller ton Mac"
        case .scanning: return "Analyse de ton Mac…"
        case .running: return "Entretien en cours…"
        case .ready: return "\(Fmt.bytes(cleanup.totalSelected)) à libérer"
        case .done: return "Ton Mac est au top ✨"
        }
    }

    private var subline: String {
        switch phase {
        case .ready: return "\(threatsToRemove) menace(s) · \(maintCount) optimisation(s) · \(updater.updates.count) mise(s) à jour"
        case .done: return report.joined(separator: " · ")
        default: return "Aura vérifie déchets, menaces, performances et mises à jour en une seule passe."
        }
    }

    // MARK: Les 4 piliers

    private var pillars: some View {
        let failedChecks = security.checks.filter { $0.ok == false }.count
        return HStack(alignment: .top, spacing: 14) {
            pillar(title: "Nettoyage", icon: "wand.and.stars", color: .blue, on: $doClean,
                   value: Fmt.bytes(cleanup.totalSelected),
                   detail: "\(cleanup.categories.filter { $0.selectedSize > 0 }.count) catégories", module: .cleanup)
            pillar(title: "Protection", icon: "shield.lefthalf.filled", color: threatsToRemove > 0 ? .red : .green, on: $doProtect,
                   value: threatsToRemove > 0 ? "\(threatsToRemove) menace(s)" : "Aucune menace",
                   detail: failedChecks == 0 ? "Réglages de sécurité OK" : "\(failedChecks) réglage(s) à corriger", module: .security)
            pillar(title: "Vitesse", icon: "bolt.fill", color: .orange, on: $doSpeed,
                   value: "\(maintCount) tâche(s)", detail: "\(apps.loginItems.count) app(s) au démarrage", module: .maintenance)
            pillar(title: "Applications", icon: "square.grid.2x2.fill", color: .cyan, on: nil,
                   value: "\(updater.updates.count) mise(s) à jour",
                   detail: "\(unusedApps.count) app(s) inutilisée(s) depuis 6 mois", module: .updater)
        }
    }

    private func pillar(title: String, icon: String, color: Color, on: Binding<Bool>?, value: String,
                        detail: String, module: Module) -> some View {
        GlassCard(padding: 16) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: icon).font(.title2).foregroundStyle(color)
                    Spacer()
                    if let on { Toggle("", isOn: on).toggleStyle(.switch).labelsHidden().controlSize(.small) }
                }
                Text(title).font(.headline)
                Text(value).font(.title3.bold()).foregroundStyle(color)
                Text(detail).font(.caption).foregroundStyle(.secondary)
                Button("Voir le détail") { goTo(module) }.buttonStyle(.borderless).font(.caption)
            }
        }
    }

    // MARK: Assistant

    struct Tip: Identifiable {
        let id: String
        let text: String
        let module: Module
    }

    private var assistant: some View {
        let tips = recommendations
        return GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                Label("Assistant", systemImage: "lightbulb.fill").font(.headline).foregroundStyle(.yellow)
                if tips.isEmpty {
                    Text("Rien à signaler pour l'instant. Lance une analyse pour des conseils personnalisés.")
                        .foregroundStyle(.secondary)
                }
                ForEach(tips) { tip in
                    Button { goTo(tip.module) } label: {
                        HStack(spacing: 10) {
                            Image(systemName: tip.module.icon).foregroundStyle(tip.module.tint).frame(width: 22)
                            Text(tip.text).font(.callout).multilineTextAlignment(.leading)
                            Spacer()
                            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.secondary)
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var recommendations: [Tip] {
        var r: [Tip] = []
        if monitor.diskTotal > 0 && Double(monitor.diskFree) / Double(monitor.diskTotal) < 0.15 {
            r.append(Tip(id: "space", text: "Ton disque est rempli à \(Int(monitor.diskUsedRatio * 100)) %. Repère ce qui pèse le plus avec la Carte de l'espace.", module: .spaceMap))
        }
        if let ios = cleanup.categories.first(where: { $0.id == "ios" }), ios.totalSize > 2_000_000_000 {
            r.append(Tip(id: "ios", text: "\(Fmt.bytes(ios.totalSize)) de sauvegardes iPhone/iPad dorment sur ton Mac.", module: .cleanup))
        }
        if !unusedApps.isEmpty {
            let size = unusedApps.reduce(Int64(0)) { $0 + $1.size }
            r.append(Tip(id: "unused", text: "\(unusedApps.count) apps non ouvertes depuis 6 mois occupent \(Fmt.bytes(size)).", module: .apps))
        }
        if !updater.updates.isEmpty {
            r.append(Tip(id: "updates", text: "\(updater.updates.count) apps ont une mise à jour : les failles corrigées te protègent.", module: .updater))
        }
        if security.checks.contains(where: { $0.id == "filevault" && $0.ok == false }) {
            r.append(Tip(id: "fv", text: "FileVault est désactivé : en cas de vol, tes données sont lisibles.", module: .security))
        }
        if apps.loginItems.count > 6 {
            r.append(Tip(id: "login", text: "\(apps.loginItems.count) apps s'ouvrent au démarrage : allège la liste pour démarrer plus vite.", module: .launch))
        }
        if !activity.idleApps.isEmpty {
            r.append(Tip(id: "idle-apps", text: "\(activity.idleApps.count) app(s) ouvertes mais inutilisées depuis plus d'une heure occupent \(Fmt.bytes(activity.idleMemory)) de mémoire.", module: .activity))
        }
        if let g = activity.greedyApps.first {
            r.append(Tip(id: "greedy", text: "\(g.name) est gourmande : \(activity.explanation(g).lowercased()).", module: .activity))
        }
        if monitor.swapUsed > 4_000_000_000 {
            r.append(Tip(id: "swap", text: "Ton Mac utilise \(Fmt.bytes(monitor.swapUsed)) de swap : ferme les apps gourmandes.", module: .monitor))
        }
        if let h = monitor.battery.health, h < 0.85 {
            r.append(Tip(id: "battery", text: "Batterie à \(Int(h * 100)) % de sa capacité d'origine.", module: .monitor))
        }
        return r
    }

    // MARK: Orchestration

    private func scanAll() async {
        phase = .scanning
        report = []
        step = "Recherche des déchets…"
        await cleanup.scan()
        step = "Vérification de sécurité…"
        let previous = security.depth
        security.depth = .quick
        await security.scan()
        security.depth = previous
        step = "Optimisations recommandées…"
        maint.selectRecommended()
        await apps.load()
        await apps.loadLoginItems()
        step = "Recherche de mises à jour…"
        await updater.check()
        phase = .ready
    }

    private func runAll() async {
        phase = .running
        if doClean {
            step = "Nettoyage…"
            await cleanup.clean()
            report.append("\(Fmt.bytes(cleanup.lastFreed)) libérés")
        }
        if doProtect && threatsToRemove > 0 {
            step = "Neutralisation des menaces…"
            let r = await security.removeSelected()
            report.append("\(r.removed) menace(s) supprimée(s)")
        }
        if doSpeed && maintCount > 0 {
            step = "Optimisation…"
            await maint.runSelected()
            report.append("\(maint.log.filter { $0.hasPrefix("✅") }.count) optimisation(s)")
        }
        phase = .done
    }
}
