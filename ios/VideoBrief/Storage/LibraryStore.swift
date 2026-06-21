import Combine
import Foundation

@MainActor
final class LibraryStore: ObservableObject {
    @Published private(set) var videos: [VideoRecord] = []
    @Published var isRefreshing = false
    @Published var isProcessing = false
    @Published var processingMessage = ""
    @Published var errorMessage: String?
    @Published var isOnline = false

    private let api = APIClient.shared
    private let cacheURL: URL

    init() {
        let root = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first!
        let folder = root.appendingPathComponent("VideoBrief", isDirectory: true)
        try? FileManager.default.createDirectory(
            at: folder,
            withIntermediateDirectories: true
        )
        cacheURL = folder.appendingPathComponent("videos.json")
        loadCache()
        Task { await refresh() }
    }

    var favorites: [VideoRecord] {
        videos.filter(\.isFavorite)
    }

    func refresh() async {
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            videos = try await api.videos()
            isOnline = true
            errorMessage = nil
            saveCache()
        } catch {
            isOnline = false
            if videos.isEmpty {
                errorMessage = error.localizedDescription
            }
        }
    }

    func submit(url: String) async -> Bool {
        isProcessing = true
        processingMessage = "正在提交视频…"
        errorMessage = nil
        defer { isProcessing = false }
        do {
            var job = try await api.process(url: url)
            processingMessage = job.message.isEmpty ? "正在生成解说…" : job.message
            for _ in 0..<600 {
                try await Task.sleep(for: .seconds(3))
                job = try await api.job(job.id)
                processingMessage = job.message
                if job.status == "completed" {
                    await refresh()
                    processingMessage = "处理完成"
                    return true
                }
                if job.status == "failed" {
                    throw APIClientError.server(job.message)
                }
            }
            throw APIClientError.server("处理时间过长，请稍后回到视频库刷新")
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    func toggleFavorite(_ video: VideoRecord) async {
        updateLocal(video.id) { $0.isFavorite.toggle() }
        do {
            let updated = try await api.update(
                videoId: video.id,
                isFavorite: !video.isFavorite
            )
            replace(updated)
        } catch {
            updateLocal(video.id) { $0.isFavorite = video.isFavorite }
            errorMessage = error.localizedDescription
        }
    }

    func markRead(_ video: VideoRecord) async {
        guard !video.isRead else { return }
        updateLocal(video.id) { $0.isRead = true }
        do {
            let updated = try await api.update(videoId: video.id, isRead: true)
            replace(updated)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func testConnection() async -> Bool {
        do {
            let online = try await api.health()
            isOnline = online
            return online
        } catch {
            isOnline = false
            errorMessage = error.localizedDescription
            return false
        }
    }

    private func replace(_ video: VideoRecord) {
        guard let index = videos.firstIndex(where: { $0.id == video.id }) else {
            videos.insert(video, at: 0)
            saveCache()
            return
        }
        videos[index] = video
        saveCache()
    }

    private func updateLocal(_ id: String, mutate: (inout VideoRecord) -> Void) {
        guard let index = videos.firstIndex(where: { $0.id == id }) else { return }
        mutate(&videos[index])
        saveCache()
    }

    private func loadCache() {
        guard let data = try? Data(contentsOf: cacheURL) else { return }
        let decoder = JSONDecoder()
        videos = (try? decoder.decode([VideoRecord].self, from: data)) ?? []
    }

    private func saveCache() {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(videos) else { return }
        try? data.write(to: cacheURL, options: .atomic)
    }
}
