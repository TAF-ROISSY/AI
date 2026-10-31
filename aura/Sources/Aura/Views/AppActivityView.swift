import SwiftUI
import AppKit

/// Petite courbe d'activité (sans le coût d'un graphique complet par ligne).
struct Sparkline: Shape {
    var values: [Double]
    var maxValue: Double = 100

    func path(in rect: CGRect) -> Path {
        var p = Path()
        guard values.count > 1 else { return p }
        let m = max(maxValue, values.max() ?? 1, 1)
        for (i, v) in values.enumerated() {
            let x = rect.minX + rect.width * CGFloat(i) / CGFloat(values.count - 1)
            let y = rect.maxY - rect.height * CGFloat(min(v, m) / m)
            if i == 0 { p.move(to: CGPoint(x: x, y: y)) } else { p.addLine(to: CGPoint(x: x, y: y)) }
        }
        return p
    }
}

enum AppSort: String, CaseIterable, Identifiable {
    case impact = "Impact", cpu = "Processeur", memory = "Mémoire", energy = "Énergie", name = "Nom"
    var id: String { rawValue }
}

struct AppActivityView: View {
    @EnvironmentObject var activity: AppActivityMonitor
    @Etat private var sort: AppSort = .impact
    @Etat private var search = ""
    @Etat private var showBackground = false
    @Etat private var expanded: Set<String> = []
    @Etat private var selection: Set<String> = []
    @Etat private var toForce: AppUsage?
    @Etat private var procToStop: ProcUsage?
    @Etat private var confirmIdle = false

    private var shown: [AppUsage] {
        var list = activity.apps.filter { showBackground || !$0.isBackground || $0.isGreedy }
        if !search.isEmpty { list = list.filter { $0.name.localizedCaseInsensitiveContains(search) } }
        switch sort {
        case .impact: return list
        case .cpu: return list.sorted { $0.cpuAvg > $1.cpuAvg }
        case .memory: return list.sorted { $0.memory > $1.memory }
        case .energy: return list.sorted { $0.energyAvg > $1.energyAvg }
        case .name: return list.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        }
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .activity, subtitle: "Ce que consomme chaque application ouverte, onglets et sous-processus compris.")

                HStack(spacing: 14) {
                    StatTile(title: "Applications ouvertes", value: "\(activity.regularApps.count)", icon: "square.stack.3d.up.fill", tint: .indigo)
                    StatTile(title: "Mémoire des apps", value: Fmt.bytes(activity.totalMemory), icon: "memorychip", tint: .purple)
                    StatTile(title: "Gourmandes", value: "\(activity.greedyApps.count)", icon: "flame.fill",
                             tint: activity.greedyApps.isEmpty ? .green : .orange)
                    StatTile(title: "Inutilisées", value: activity.idleApps.isEmpty ? "0" : "\(activity.idleApps.count) · \(Fmt.bytes(activity.idleMemory))",
                             icon: "moon.zzz.fill", tint: .gray)
                }

                analysisCard

                HStack(spacing: 12) {
                    TextField("Rechercher une app", text: $search).textFieldStyle(.roundedBorder).frame(width: 220)
                    Picker("Trier par", selection: $sort) { ForEach(AppSort.allCases) { Text($0.rawValue).tag($0) } }
                        .pickerStyle(.segmented).frame(width: 400)
                    Toggle("Apps en arrière-plan", isOn: $showBackground).toggleStyle(.checkbox)
                    Spacer()
                    if !selection.isEmpty {
                        Button("Quitter la sélection (\(selection.count))") {
                            activity.quit(ids: selection)
                            selection = []
                        }
                        .buttonStyle(.borderedProminent).tint(.red)
                    }
                }
                if !activity.message.isEmpty {
                    Text(activity.message).font(.callout).foregroundStyle(.green).frame(maxWidth: .infinity, alignment: .leading)
                }

                GlassCard(padding: 8) {
                    VStack(spacing: 0) {
                        header
                        Divider().opacity(0.2)
                        if activity.lastUpdate == nil {
                            ProgressView("Analyse des applications…").padding(30)
                        }
                        LazyVStack(spacing: 0) {
                            ForEach(shown) { a in
                                row(a)
                                if expanded.contains(a.id) { details(a) }
                                Divider().opacity(0.1)
                            }
                        }
                    }
                }
                Text("Mesures en direct toutes les 2 secondes. Le processeur est exprimé en % d'un cœur : une app peut dépasser 100 % sur plusieurs cœurs.")
                    .font(.caption2).foregroundStyle(.tertiary).frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(28)
        }
        .onAppear { activity.beginLive() }
        .onDisappear { activity.endLive() }
        .confirmationDialog("Forcer \(toForce?.name ?? "") à quitter ?", isPresented: Binding(
            get: { toForce != nil }, set: { if !$0 { toForce = nil } })) {
            Button("Forcer à quitter", role: .destructive) { if let a = toForce { activity.quit(a, force: true) } }
        } message: {
            Text("Les documents non enregistrés dans cette application seront perdus.")
        }
        .confirmationDialog("Arrêter le processus \(procToStop?.name ?? "") ?", isPresented: Binding(
            get: { procToStop != nil }, set: { if !$0 { procToStop = nil } })) {
            Button("Arrêter") { if let p = procToStop { activity.stopProcess(p.pid, force: false) } }
            Button("Forcer l'arrêt", role: .destructive) { if let p = procToStop { activity.stopProcess(p.pid, force: true) } }
        } message: {
            Text("Pour un onglet de navigateur, la page se rechargera. L'application principale continue de tourner.")
        }
        .confirmationDialog("Fermer \(activity.idleApps.count) application(s) inutilisée(s) ?", isPresented: $confirmIdle) {
            Button("Fermer") { activity.quitIdleApps() }
        } message: {
            Text("Chaque application te demandera d'enregistrer tes documents si besoin.")
        }
    }

    // MARK: Analyse

    private var analysisCard: some View {
        let flagged = activity.apps.filter { !$0.flags.isEmpty }
        return GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Label("Analyse", systemImage: "stethoscope").font(.headline)
                    Spacer()
                    if !activity.idleApps.isEmpty {
                        Button("Fermer les apps inutilisées (\(Fmt.bytes(activity.idleMemory)) libérés)") { confirmIdle = true }
                            .buttonStyle(.borderedProminent).tint(.indigo)
                    }
                }
                if flagged.isEmpty {
                    Label(activity.lastUpdate == nil ? "Analyse en cours…" : "Aucune application gourmande en ce moment.",
                          systemImage: "checkmark.seal.fill").foregroundStyle(.green)
                } else {
                    ForEach(flagged.prefix(6)) { a in
                        HStack(spacing: 10) {
                            Image(nsImage: a.icon).resizable().frame(width: 24, height: 24)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(a.name).fontWeight(.semibold)
                                Text(activity.explanation(a)).font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            ForEach(a.flags, id: \.self) { flagChip($0) }
                            quitButton(a)
                        }
                    }
                }
            }
        }
    }

    // MARK: Tableau

    private var header: some View {
        HStack(spacing: 12) {
            Color.clear.frame(width: 22)
            Text("Application").frame(maxWidth: .infinity, alignment: .leading)
            Text("Activité").frame(width: 90)
            Text("Processeur").frame(width: 80, alignment: .trailing)
            Text("Mémoire").frame(width: 85, alignment: .trailing)
            Text("Énergie").frame(width: 65, alignment: .trailing)
            Color.clear.frame(width: 190)
        }
        .font(.caption.weight(.semibold)).foregroundStyle(.secondary)
        .padding(.horizontal, 8).padding(.vertical, 6)
    }

    private func row(_ a: AppUsage) -> some View {
        HStack(spacing: 12) {
            if a.canQuit {
                Button {
                    if selection.contains(a.id) { selection.remove(a.id) } else { selection.insert(a.id) }
                } label: { CheckCircle(on: selection.contains(a.id), tint: .red).font(.body) }
                .buttonStyle(.plain).frame(width: 22)
            } else {
                Color.clear.frame(width: 22)
            }
            HStack(spacing: 10) {
                Image(nsImage: a.icon).resizable().frame(width: 30, height: 30)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(a.name).fontWeight(.medium).lineLimit(1)
                        if a.isFrontmost { Text("au premier plan").font(.caption2).foregroundStyle(.green) }
                        ForEach(a.flags, id: \.self) { flagChip($0) }
                    }
                    Text(subtitle(a)).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
            .onTapGesture { toggleExpand(a) }

            Sparkline(values: a.history, maxValue: 100)
                .stroke(cpuColor(a.cpuAvg), style: StrokeStyle(lineWidth: 1.5, lineJoin: .round))
                .frame(width: 90, height: 22)
            Text(String(format: "%.0f %%", a.cpu)).monospacedDigit()
                .foregroundStyle(cpuColor(a.cpuAvg)).frame(width: 80, alignment: .trailing)
            Text(Fmt.bytes(a.memory)).monospacedDigit()
                .foregroundStyle(a.flags.contains(.memory) ? .purple : .primary).frame(width: 85, alignment: .trailing)
            Text(AppActivityMonitor.watts(a.energy)).monospacedDigit().font(.callout)
                .foregroundStyle(a.flags.contains(.energy) ? .yellow : .secondary).frame(width: 65, alignment: .trailing)
            HStack(spacing: 6) {
                if a.app != nil && !a.isBackground && !a.isHidden && !a.isFrontmost {
                    Button { activity.hide(a) } label: { Image(systemName: "eye.slash") }
                        .buttonStyle(.borderless).help("Masquer")
                }
                quitButton(a)
                Button { toggleExpand(a) } label: {
                    Image(systemName: "chevron.down").rotationEffect(.degrees(expanded.contains(a.id) ? 180 : 0))
                }
                .buttonStyle(.borderless)
            }
            .frame(width: 190, alignment: .trailing)
        }
        .font(.callout)
        .padding(.horizontal, 8).padding(.vertical, 7)
        .background(a.isGreedy ? Color.orange.opacity(0.07) : .clear)
    }

    @ViewBuilder
    private func quitButton(_ a: AppUsage) -> some View {
        if !a.canQuit {
            EmptyView()
        } else if activity.isStuck(a) {
            Button("Forcer") { toForce = a }.buttonStyle(.borderedProminent).tint(.red).controlSize(.small)
                .help("L'application ne répond pas à la demande de fermeture")
        } else if activity.isQuitting(a) {
            ProgressView().controlSize(.small)
        } else {
            Menu {
                Button("Quitter") { activity.quit(a) }
                Button("Forcer à quitter…") { toForce = a }
            } label: {
                Text("Quitter")
            } primaryAction: {
                activity.quit(a)
            }
            .menuStyle(.borderedButton).controlSize(.small).fixedSize()
        }
    }

    private func details(_ a: AppUsage) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 16) {
                if let d = a.launchDate { Label("Ouverte \(Fmt.relativeDate(d))", systemImage: "clock") }
                Label("Disque : ↓ \(Fmt.rate(a.diskRead))  ↑ \(Fmt.rate(a.diskWrite))", systemImage: "internaldrive")
                Label("Moyenne processeur : \(Int(a.cpuAvg)) %", systemImage: "cpu")
                Spacer()
                if let p = a.iconPath, a.app != nil {
                    Button("Afficher dans le Finder") { FS.reveal(URL(fileURLWithPath: p)) }.buttonStyle(.borderless)
                }
                Button("Moniteur d'activité") {
                    NSWorkspace.shared.open(URL(fileURLWithPath: "/System/Applications/Utilities/Activity Monitor.app"))
                }
                .buttonStyle(.borderless)
            }
            .font(.caption).foregroundStyle(.secondary)

            Text("\(a.processes.count) processus").font(.caption.weight(.semibold))
            ForEach(a.processes.prefix(20)) { p in
                HStack(spacing: 10) {
                    Image(systemName: "gearshape").font(.caption).foregroundStyle(.tertiary)
                    Text(p.name).font(.caption).lineLimit(1).truncationMode(.middle)
                    Text("PID \(p.pid)").font(.caption2).foregroundStyle(.tertiary)
                    Spacer()
                    Text(String(format: "%.1f %%", p.cpu)).font(.caption.monospacedDigit()).frame(width: 60, alignment: .trailing)
                    Text(Fmt.bytes(p.memory)).font(.caption.monospacedDigit()).frame(width: 80, alignment: .trailing)
                    if p.pid != a.pid && p.pid != getpid() {
                        Button { procToStop = p } label: { Image(systemName: "xmark.circle") }
                            .buttonStyle(.borderless).help("Arrêter ce processus")
                    } else {
                        Color.clear.frame(width: 16)
                    }
                }
            }
            if a.processes.count > 20 {
                Text("+ \(a.processes.count - 20) autres processus").font(.caption2).foregroundStyle(.tertiary)
            }
        }
        .padding(.leading, 74).padding(.trailing, 12).padding(.vertical, 8)
        .background(Color.white.opacity(0.03))
    }

    // MARK: Utilitaires

    private func flagChip(_ f: AppFlag) -> some View {
        Label(f.label, systemImage: f.icon)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(f.color.opacity(0.25), in: Capsule())
            .foregroundStyle(f.color)
    }

    private func subtitle(_ a: AppUsage) -> String {
        var parts: [String] = []
        if a.processes.count > 1 { parts.append("\(a.processes.count) processus") }
        if a.isBackground { parts.append("arrière-plan") }
        if a.isHidden { parts.append("masquée") }
        if let m = a.idleMinutes, m >= 5, !a.isFrontmost {
            parts.append(m >= 120 ? "inactive depuis \(m / 60) h" : "inactive depuis \(m) min")
        }
        return parts.isEmpty ? "Active" : parts.joined(separator: " · ")
    }

    private func cpuColor(_ v: Double) -> Color {
        v > 80 ? .red : v > 40 ? .orange : v > 10 ? .yellow : .green
    }

    private func toggleExpand(_ a: AppUsage) {
        if expanded.contains(a.id) { expanded.remove(a.id) } else { expanded.insert(a.id) }
    }
}
