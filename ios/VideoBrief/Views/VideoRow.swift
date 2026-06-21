import SwiftUI

struct VideoRow: View {
    let video: VideoRecord

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            AsyncImage(url: video.thumbnailURL) { phase in
                switch phase {
                case .success(let image):
                    image.resizable().scaledToFill()
                default:
                    Rectangle()
                        .fill(Color.secondary.opacity(0.12))
                        .overlay {
                            Image(systemName: "play.fill")
                                .foregroundStyle(.secondary)
                        }
                }
            }
            .frame(width: 124, height: 70)
            .clipShape(RoundedRectangle(cornerRadius: 6))

            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .top) {
                    Text(video.title)
                        .font(.headline)
                        .lineLimit(2)
                    if video.isFavorite {
                        Image(systemName: "bookmark.fill")
                            .font(.caption)
                            .foregroundStyle(.red)
                    }
                }

                Text(video.summary)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)

                HStack(spacing: 8) {
                    Label(video.minutesLabel, systemImage: "clock")
                    if !video.isRead {
                        Text("未读")
                            .foregroundStyle(.blue)
                    }
                }
                .font(.caption2)
                .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 5)
    }
}
