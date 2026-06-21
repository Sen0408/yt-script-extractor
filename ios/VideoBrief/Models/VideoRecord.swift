import Foundation

struct VideoRecord: Codable, Identifiable, Hashable {
    let videoId: String
    var title: String
    let url: String
    let language: String
    let summary: String
    let keyPoints: [String]
    let deepDive: String
    let aiComments: String
    let topics: [String]
    let transcript: String
    let wordCount: Int
    let watchMinutes: Double
    let analysisMethod: String
    let thumbnailUrl: String
    let notionUrl: String?
    let folderPath: String?
    let status: String
    var isFavorite: Bool
    var isRead: Bool
    let createdAt: String
    let updatedAt: String

    var id: String { videoId }
    var thumbnailURL: URL? { URL(string: thumbnailUrl) }
    var youtubeURL: URL? { URL(string: url) }
    var notionURL: URL? { notionUrl.flatMap(URL.init(string:)) }
    var minutesLabel: String { "\(Int(watchMinutes.rounded())) 分钟" }
}

struct VideoListResponse: Codable {
    let items: [VideoRecord]
    let count: Int
}

struct ProcessingJob: Codable, Identifiable {
    let jobId: String
    let videoId: String?
    let sourceUrl: String
    let status: String
    let message: String
    let createdAt: String
    let updatedAt: String

    var id: String { jobId }
}

struct ProcessVideoRequest: Codable {
    let url: String
    let translate: Bool
    let language: String
}

struct VideoStateRequest: Codable {
    let isFavorite: Bool?
    let isRead: Bool?
}
