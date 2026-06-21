import Foundation

enum ServerConfiguration {
    static let storageKey = "serverURL"
    static let remoteDiscoveryURL = URL(
        string: "https://gist.githubusercontent.com/Sen0408/0b9144dcaf55de408887209419baf58b/raw/videobrief-endpoint.json"
    )!

    static var defaultURL: String {
#if targetEnvironment(simulator)
        "http://127.0.0.1:8765"
#else
        "http://Sens-Mac-mini.ad.analog.com:8765"
#endif
    }

    static var currentURL: String {
        let stored = UserDefaults.standard.string(forKey: storageKey)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return stored?.isEmpty == false ? stored! : defaultURL
    }

    static var candidateURLs: [String] {
#if targetEnvironment(simulator)
        let candidates = [currentURL, "http://127.0.0.1:8765"]
#else
        let candidates = [
            currentURL,
            "http://Sens-Mac-mini.ad.analog.com:8765",
            "http://10.20.16.23:8765",
            "http://Sens-Mac-mini.local:8765",
        ]
#endif

        return candidates.reduce(into: [String]()) { result, candidate in
            let normalized = candidate.trimmingCharacters(
                in: .whitespacesAndNewlines
            )
            guard !normalized.isEmpty, !result.contains(normalized) else {
                return
            }
            result.append(normalized)
        }
    }

    static func remember(_ url: String) {
        guard currentURL != url else { return }
        UserDefaults.standard.set(url, forKey: storageKey)
    }

    static var apiToken: String {
        guard
            let url = Bundle.main.url(
                forResource: "Secrets",
                withExtension: "plist"
            ),
            let data = try? Data(contentsOf: url),
            let values = try? PropertyListSerialization.propertyList(
                from: data,
                format: nil
            ) as? [String: Any]
        else {
            return ""
        }
        return values["VideoBriefAPIToken"] as? String ?? ""
    }
}
