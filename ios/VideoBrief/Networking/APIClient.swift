import Foundation

enum APIClientError: LocalizedError {
    case invalidServerURL
    case invalidResponse
    case connectionFailed
    case server(String)

    var errorDescription: String? {
        switch self {
        case .invalidServerURL:
            return "服务器地址无效"
        case .invalidResponse:
            return "服务器返回了无法识别的数据"
        case .connectionFailed:
            return "无法连接 VideoBrief 服务。请确认 Mac 已开机并联网，然后稍后重试。"
        case .server(let message):
            return message
        }
    }
}

actor APIClient {
    static let shared = APIClient()

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    private struct RemoteEndpoint: Decodable {
        let url: String
    }

    private func serverURLs() async -> [String] {
        var urls = ServerConfiguration.candidateURLs
        var discoveryRequest = URLRequest(
            url: ServerConfiguration.remoteDiscoveryURL
        )
        discoveryRequest.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        discoveryRequest.timeoutInterval = 8

        if
            let (data, response) = try? await URLSession.shared.data(
                for: discoveryRequest
            ),
            let http = response as? HTTPURLResponse,
            200..<300 ~= http.statusCode,
            let endpoint = try? decoder.decode(RemoteEndpoint.self, from: data),
            let remoteURL = URL(string: endpoint.url),
            remoteURL.scheme == "https"
        {
            urls.removeAll { $0 == endpoint.url }
            urls.insert(endpoint.url, at: 0)
        }
        return urls
    }

    private func request<T: Decodable>(
        _ path: String,
        method: String = "GET",
        body: Data? = nil
    ) async throws -> T {
        var attemptedValidURL = false

        for serverURL in await serverURLs() {
            guard
                let baseURL = URL(string: serverURL),
                let url = URL(string: path, relativeTo: baseURL)
            else {
                continue
            }
            attemptedValidURL = true

            var request = URLRequest(url: url)
            request.httpMethod = method
            request.httpBody = body
            request.timeoutInterval = 12
            if body != nil {
                request.setValue(
                    "application/json",
                    forHTTPHeaderField: "Content-Type"
                )
            }
            if !ServerConfiguration.apiToken.isEmpty {
                request.setValue(
                    ServerConfiguration.apiToken,
                    forHTTPHeaderField: "X-VideoBrief-Token"
                )
            }

            let attemptCount = serverURL.hasSuffix(".trycloudflare.com")
                ? 3
                : 1
            for attempt in 0..<attemptCount {
                do {
                    let (data, response) = try await URLSession.shared.data(
                        for: request
                    )
                    guard let http = response as? HTTPURLResponse else {
                        throw APIClientError.invalidResponse
                    }
                    guard 200..<300 ~= http.statusCode else {
                        let detail = (
                            try? JSONSerialization.jsonObject(with: data)
                                as? [String: Any]
                        )?["detail"]
                        throw APIClientError.server(
                            detail as? String
                                ?? "服务器错误：\(http.statusCode)"
                        )
                    }
                    let decoded = try decoder.decode(T.self, from: data)
                    ServerConfiguration.remember(serverURL)
                    return decoded
                } catch let error as APIClientError {
                    if case .server = error {
                        throw error
                    }
                } catch {
                    // Try the next attempt or fallback server below.
                }

                if attempt + 1 < attemptCount {
                    try? await Task.sleep(for: .seconds(2))
                }
            }
        }

        throw attemptedValidURL
            ? APIClientError.connectionFailed
            : APIClientError.invalidServerURL
    }

    func health() async throws -> Bool {
        struct Health: Decodable { let status: String }
        let result: Health = try await request("/api/health")
        return result.status == "ok"
    }

    func videos() async throws -> [VideoRecord] {
        let response: VideoListResponse = try await request("/api/videos")
        return response.items
    }

    func process(url: String) async throws -> ProcessingJob {
        let payload = ProcessVideoRequest(url: url, translate: false, language: "zh-Hans")
        return try await request(
            "/api/videos/process",
            method: "POST",
            body: encoder.encode(payload)
        )
    }

    func job(_ id: String) async throws -> ProcessingJob {
        try await request("/api/jobs/\(id)")
    }

    func update(
        videoId: String,
        isFavorite: Bool? = nil,
        isRead: Bool? = nil
    ) async throws -> VideoRecord {
        let payload = VideoStateRequest(isFavorite: isFavorite, isRead: isRead)
        return try await request(
            "/api/videos/\(videoId)",
            method: "PATCH",
            body: encoder.encode(payload)
        )
    }
}
