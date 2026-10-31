import SwiftUI
import AppKit

struct PhotoOrganizerView: View {
    @EnvironmentObject var org: PhotoOrganizer
    @EnvironmentObject var router: Router
    @EnvironmentObject var volumes: VolumeManager
    @Etat private var confirm = false
    @Etat private var showDuplicates = false
    @Etat private var showOutside = false

    private static let zones: [(String, String)] = [
        ("Europe/Paris", "France (Paris)"), ("Asia/Bangkok", "Thaïlande, Vietnam, Cambodge"),
        ("Asia/Makassar", "Bali"), ("Asia/Singapore", "Singapour, Malaisie"), ("Asia/Tokyo", "Japon"),
        ("Asia/Hong_Kong", "Hong Kong, Chine"), ("Asia/Kolkata", "Inde"), ("Asia/Dubai", "Dubaï"),
        ("Indian/Maldives", "Maldives"), ("Indian/Mauritius", "Maurice"), ("Indian/Reunion", "La Réunion"),
        ("Africa/Casablanca", "Maroc"), ("Africa/Cairo", "Égypte"), ("Europe/Istanbul", "Turquie"),
        ("Europe/Lisbon", "Portugal"), ("Europe/London", "Royaume-Uni"), ("Atlantic/Reykjavik", "Islande"),
        ("America/New_York", "New York, Montréal"), ("America/Los_Angeles", "Californie"),
        ("America/Guadeloupe", "Guadeloupe, Martinique"), ("Pacific/Tahiti", "Polynésie"), ("Australia/Sydney", "Sydney")
    ]

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                ModuleHeader(module: .voyages, subtitle: "Donne les étapes de ton voyage : Aura crée les dossiers (Thaïlande › Bangkok › Bangkok 1), y range tes photos et vidéos d'après leur date de prise de vue, et écarte les doublons.")

                HStack(alignment: .top, spacing: 14) {
                    programCard.frame(width: 480)
                    sourcesCard
                }

                if org.isWorking || !org.status.isEmpty {
                    HStack(spacing: 12) {
                        if org.isWorking { ProgressView(value: org.progress).frame(width: 220) }
                        Text(org.status).foregroundStyle(.secondary)
                        Spacer()
                        if !org.lastBatch.isEmpty && !org.isWorking {
                            Button("Annuler le dernier classement (\(org.lastBatch.count))") { Task { await org.undo() } }
                        }
                    }
                }

                if let plan = org.plan { preview(plan) }
            }
            .padding(28)
        }
        .onAppear {
            let r = router.consumeRoots()
            if !r.isEmpty { org.sources = r; org.plan = nil }
        }
        .confirmationDialog(org.transfer == .move ? "Classer \(org.plan?.totalFiles ?? 0) fichier(s) ?" : "Copier \(org.plan?.totalFiles ?? 0) fichier(s) ?",
                            isPresented: $confirm) {
            Button(org.transfer == .move ? "Classer" : "Copier") { Task { await org.apply() } }
        } message: {
            Text("Destination : \(org.plan?.tripRoot?.path ?? ""). Aucun fichier n'est écrasé, et tu pourras tout annuler.")
        }
    }

    // MARK: Programme du voyage

    private var programCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Programme du voyage").font(.auraHeadline)
                    Spacer()
                    Menu("Voyages") {
                        Button("Nouveau voyage") { org.newTrip() }
                        if !org.trips.isEmpty {
                            Divider()
                            ForEach(org.trips) { t in
                                Button(t.name) { org.saveTrip(); org.current = t; org.plan = nil }
                            }
                            Divider()
                            Menu("Supprimer") {
                                ForEach(org.trips) { t in Button(t.name) { org.deleteTrip(t) } }
                            }
                        }
                    }
                    .fixedSize()
                }

                LabeledContent("Nom du dossier") {
                    TextField("Thaïlande", text: $org.current.name).textFieldStyle(.roundedBorder).frame(width: 260)
                }
                LabeledContent("Heure locale") {
                    Picker("", selection: $org.current.timeZoneID) {
                        if !Self.zones.contains(where: { $0.0 == org.current.timeZoneID }) {
                            Text(org.current.timeZoneID).tag(org.current.timeZoneID)
                        }
                        ForEach(Self.zones, id: \.0) { Text($0.1).tag($0.0) }
                    }
                    .labelsHidden().frame(width: 260)
                }

                Divider().opacity(0.3)
                Text("Une ligne par étape : à partir de cette date (et heure), tu es à ce lieu, jusqu'à l'étape suivante.")
                    .font(.auraCaption).foregroundStyle(.secondary)

                ForEach($org.current.stages) { $stage in
                    HStack(spacing: 8) {
                        DatePicker("", selection: $stage.start, displayedComponents: [.date, .hourAndMinute])
                            .labelsHidden()
                        TextField("Lieu (ex. Bangkok)", text: $stage.place).textFieldStyle(.roundedBorder)
                        Button {
                            org.current.stages.removeAll { $0.id == stage.id }
                        } label: { Image(systemName: "minus.circle") }
                        .buttonStyle(.borderless)
                        .disabled(org.current.stages.count <= 1)
                    }
                }
                HStack {
                    Button { org.addStage() } label: { Label("Ajouter une étape", systemImage: "plus") }
                    Spacer()
                    Text("Fin du voyage").foregroundStyle(.secondary)
                    DatePicker("", selection: $org.current.end, displayedComponents: [.date, .hourAndMinute]).labelsHidden()
                }
            }
            .environment(\.timeZone, org.current.timeZone)
        }
    }

    // MARK: Photos à classer

    private var sourcesCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Photos à classer").font(.auraHeadline)
                    Spacer()
                    Menu {
                        ForEach(volumes.externalVolumes) { v in
                            Button { add(v.url) } label: { Label(v.name, systemImage: v.symbol) }
                        }
                        if !volumes.externalVolumes.isEmpty { Divider() }
                        Button("Choisir un dossier…") { if let u = pickFolder() { add(u) } }
                        Button("Images du Mac") { add(FS.url("~/Pictures")) }
                    } label: { Label("Ajouter", systemImage: "plus") }
                    .fixedSize()
                }
                if org.sources.isEmpty {
                    Text("Ajoute une carte SD, une clé USB ou un dossier.").foregroundStyle(.secondary)
                } else {
                    FlowChips(items: org.sources.map { RootChip(url: $0, label: label(for: $0)) }) { u in
                        org.sources.removeAll { $0 == u }
                        org.plan = nil
                    }
                }

                LabeledContent("Ranger dans") {
                    HStack {
                        Text(org.suggestedDestination.path.replacingOccurrences(of: FS.home.path, with: "~"))
                            .lineLimit(1).truncationMode(.head).foregroundStyle(.secondary)
                        Button("Changer…") { if let u = pickFolder(start: org.suggestedDestination) { org.destination = u } }
                            .controlSize(.small)
                    }
                }

                Picker("Fichiers", selection: $org.transfer) { ForEach(TransferMode.allCases) { Text($0.rawValue).tag($0) } }
                Picker("Sous-dossiers", selection: $org.subfolders) { ForEach(SubfolderMode.allCases) { Text($0.rawValue).tag($0) } }
                Picker("Doublons", selection: $org.duplicateAction) { ForEach(DuplicateAction.allCases) { Text($0.rawValue).tag($0) } }
                Toggle("Renommer les fichiers (Bangkok 1 - 001.heic…)", isOn: $org.rename).toggleStyle(.checkbox)
                Toggle("Mettre les vidéos dans un sous-dossier « Vidéos »", isOn: $org.separateVideos).toggleStyle(.checkbox)
                Toggle("Classer aussi les photos prises hors des dates du voyage (dossier « Autres dates »)", isOn: $org.includeOutside)
                    .toggleStyle(.checkbox)

                HStack {
                    Spacer()
                    BigButton(title: org.isWorking ? "Analyse…" : "Analyser", icon: "sparkle.magnifyingglass", busy: org.isWorking) {
                        Task { await org.analyze() }
                    }
                    .disabled(org.sources.isEmpty)
                }
            }
        }
    }

    // MARK: Aperçu

    private func preview(_ plan: OrganizePlan) -> some View {
        let photos = plan.folders.reduce(0) { $0 + $1.photos }
        let videos = plan.folders.reduce(0) { $0 + $1.videos }
        return VStack(spacing: 14) {
            HStack(spacing: 14) {
                StatTile(title: "Photos", value: "\(photos)", icon: "photo")
                StatTile(title: "Vidéos", value: "\(videos)", icon: "video")
                StatTile(title: "Dossiers", value: "\(plan.folders.count)", icon: "folder")
                StatTile(title: "Doublons écartés", value: "\(plan.duplicates.count)", icon: "square.on.square",
                         tint: plan.duplicates.isEmpty ? AuraTheme.legend : AuraTheme.amber)
            }

            GlassCard(padding: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Image(systemName: "folder.fill").foregroundStyle(AuraTheme.signal)
                        Text(plan.tripRoot?.lastPathComponent ?? "").font(.auraHeadline)
                        Text(plan.tripRoot?.deletingLastPathComponent().path.replacingOccurrences(of: FS.home.path, with: "~") ?? "")
                            .font(.auraCaption).foregroundStyle(.tertiary)
                        Spacer()
                        BigButton(title: org.transfer == .move ? "Classer \(plan.totalFiles) fichiers" : "Copier \(plan.totalFiles) fichiers",
                                  icon: "tray.and.arrow.down.fill", busy: org.isWorking) { confirm = true }
                            .disabled(plan.totalFiles == 0)
                    }
                    .padding(.bottom, 6)
                    ForEach(cities(plan), id: \.self) { city in
                        cityBlock(city, folders: plan.folders.filter { $0.path.components(separatedBy: "/").first == city })
                    }
                }
            }

            if !plan.duplicates.isEmpty {
                GlassCard(padding: 12) {
                    DisclosureGroup(isExpanded: $showDuplicates) {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(Array(plan.duplicates.prefix(200).enumerated()), id: \.offset) { pair in
                                HStack(spacing: 8) {
                                    Text(pair.element.copy.lastPathComponent).lineLimit(1)
                                    Text("identique à").foregroundStyle(.tertiary)
                                    Text(pair.element.original.lastPathComponent).lineLimit(1).foregroundStyle(.secondary)
                                    Spacer()
                                    Button { FS.reveal(pair.element.copy) } label: { Image(systemName: "magnifyingglass") }
                                        .buttonStyle(.borderless)
                                }
                                .font(.auraCaption)
                            }
                        }
                        .padding(.top, 6)
                    } label: {
                        Text("\(plan.duplicates.count) doublon(s) au contenu identique : \(org.duplicateAction.rawValue.lowercased())")
                    }
                }
            }

            if !plan.outside.isEmpty || !plan.undated.isEmpty {
                GlassCard(padding: 12) {
                    DisclosureGroup(isExpanded: $showOutside) {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach((plan.outside + plan.undated).prefix(200)) { m in
                                HStack {
                                    Text(m.url.lastPathComponent).lineLimit(1)
                                    Spacer()
                                    Text(m.date.map { format($0) } ?? "sans date").foregroundStyle(.secondary)
                                }
                                .font(.auraCaption)
                            }
                        }
                        .padding(.top, 6)
                    } label: {
                        Text("\(plan.outside.count + plan.undated.count) fichier(s) hors des dates du voyage, laissés à leur place")
                    }
                }
            }
        }
    }

    private func cities(_ plan: OrganizePlan) -> [String] {
        var seen: [String] = []
        for f in plan.folders {
            let c = f.path.components(separatedBy: "/").first ?? f.path
            if !seen.contains(c) { seen.append(c) }
        }
        return seen
    }

    private func cityBlock(_ city: String, folders: [PlannedFolder]) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 6) {
                Image(systemName: "mappin.and.ellipse").foregroundStyle(AuraTheme.legendDim)
                Text(city).font(.auraHeadline)
                Text("\(folders.reduce(0) { $0 + $1.files.count }) fichiers").font(.auraCaption).foregroundStyle(.tertiary)
            }
            .padding(.top, 8)
            ForEach(folders) { f in
                HStack(spacing: 12) {
                    Image(systemName: "folder").foregroundStyle(AuraTheme.legendDim)
                    Text((f.path as NSString).lastPathComponent).frame(width: 150, alignment: .leading).lineLimit(1)
                    Text(f.firstDate.map { format($0) } ?? "").font(.auraCaption).foregroundStyle(.secondary)
                        .frame(width: 110, alignment: .leading)
                    Text("\(f.photos) photo(s)\(f.videos > 0 ? " · \(f.videos) vidéo(s)" : "")")
                        .font(.auraCaption).foregroundStyle(.secondary).frame(width: 160, alignment: .leading)
                    HStack(spacing: 4) {
                        ForEach(f.files.filter { !$0.isVideo }.prefix(6)) { file in
                            ThumbnailView(url: file.source)
                                .frame(width: 34, height: 34)
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                        }
                    }
                    Spacer()
                }
                .padding(.leading, 22).padding(.vertical, 3)
            }
        }
    }

    // MARK: Utilitaires

    private func add(_ u: URL) {
        if !org.sources.contains(u) { org.sources.append(u); org.plan = nil }
    }

    private func label(for u: URL) -> String {
        if let v = volumes.volumes.first(where: { $0.url.standardizedFileURL == u.standardizedFileURL }) { return "💾 " + v.name }
        return u.path.replacingOccurrences(of: FS.home.path, with: "~")
    }

    private func format(_ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_FR")
        f.timeZone = org.current.timeZone
        f.dateFormat = "EEE d MMM"
        return f.string(from: d)
    }
}
