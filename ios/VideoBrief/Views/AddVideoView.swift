import SwiftUI

struct AddVideoView: View {
    @EnvironmentObject private var store: LibraryStore
    @Environment(\.dismiss) private var dismiss
    @State private var url = ""
    @State private var clipboardDetected = false

    private var normalizedURL: String {
        url.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var isYouTubeURL: Bool {
        guard let parsed = URL(string: normalizedURL),
              let host = parsed.host?.lowercased() else {
            return false
        }
        return host == "youtu.be"
            || host.hasSuffix("youtube.com")
            || host.hasSuffix("youtube-nocookie.com")
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("YouTube 链接") {
                    TextField("https://www.youtube.com/watch?v=…", text: $url)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()

                    Button("从剪贴板粘贴", systemImage: "doc.on.clipboard") {
                        fillFromClipboard()
                    }

                    if clipboardDetected {
                        Label("已识别剪贴板中的 YouTube 链接", systemImage: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundStyle(.green)
                    } else if !normalizedURL.isEmpty && !isYouTubeURL {
                        Label("请输入有效的 YouTube 链接", systemImage: "exclamationmark.triangle.fill")
                            .font(.caption)
                            .foregroundStyle(.orange)
                    }
                }

                Section {
                    Button {
                        Task {
                            if await store.submit(url: normalizedURL) {
                                dismiss()
                            }
                        }
                    } label: {
                        HStack {
                            Spacer()
                            if store.isProcessing {
                                ProgressView()
                                Text(store.processingMessage)
                            } else {
                                Text("生成解说并保存")
                                    .fontWeight(.semibold)
                            }
                            Spacer()
                        }
                    }
                    .disabled(!isYouTubeURL || store.isProcessing)
                } footer: {
                    Text("Mac 会提取字幕、生成分析，同时保存到 App 视频库和 Notion。")
                }
            }
            .navigationTitle("添加视频")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") { dismiss() }
                }
            }
            .interactiveDismissDisabled(store.isProcessing)
            .task {
                if normalizedURL.isEmpty {
                    fillFromClipboard()
                }
            }
        }
    }

    private func fillFromClipboard() {
        guard let value = UIPasteboard.general.string?
            .trimmingCharacters(in: .whitespacesAndNewlines),
              let parsed = URL(string: value),
              let host = parsed.host?.lowercased(),
              host == "youtu.be"
                || host.hasSuffix("youtube.com")
                || host.hasSuffix("youtube-nocookie.com") else {
            clipboardDetected = false
            return
        }
        url = value
        clipboardDetected = true
    }
}
