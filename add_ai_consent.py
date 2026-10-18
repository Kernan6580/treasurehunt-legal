#!/usr/bin/env python3
"""Ask before sending photos to the AI (Apple guideline 5.1.2(i)); makes the new privacy policy true.
Patches 3 files with exact anchors; aborts before writing if any anchor is missing. Backups: *.bak-consent"""
import os, shutil, sys
ROOT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Desktop/TreasureHunt GOOD/TreasureHunt")
def find(name):
    hits = [os.path.join(d, name) for d, _, fs in os.walk(ROOT) if name in fs and ".bak" not in d]
    if len(hits) != 1: sys.exit(f"ABORT: expected 1 {name}, found {len(hits)}. Nothing changed.")
    return hits[0]

SHEET = r'''

// MARK: - AI consent (asked once, before the first photo leaves the phone)

enum AIConsent {
    private static let key = "th.aiConsent.v1"
    static var granted: Bool { UserDefaults.standard.bool(forKey: key) }
    static func grant() { UserDefaults.standard.set(true, forKey: key) }
}

struct AIConsentSheet: View {
    var onAllow: () -> Void
    var onDecline: () -> Void = {}
    @Environment(\.dismiss) private var dismiss
    @State private var allowed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Image(systemName: "sparkles")
                .font(.system(size: 22, weight: .semibold)).foregroundStyle(THStyle.goldText)
                .frame(width: 48, height: 48).background(THStyle.parchment).clipShape(Circle())
            Text("Send photos for identification?")
                .font(THStyle.display(26, .semibold)).foregroundStyle(THStyle.ink)
                .fixedSize(horizontal: false, vertical: true)
            Text("To identify an item or read a sale sign, TreasureHunt sends a smaller copy of your photo, plus any barcode or label text, through its server to Anthropic's Claude AI. Our server doesn't keep the photos, and Anthropic doesn't use them to train its models.")
                .font(THStyle.ui(16)).foregroundStyle(THStyle.secondary)
                .fixedSize(horizontal: false, vertical: true)
            Text("Your scans and inventory stay on your iPhone either way.")
                .font(THStyle.ui(15)).foregroundStyle(THStyle.ink)
            if let url = URL(string: "https://kernan6580.github.io/treasurehunt-legal/privacy.html") {
                Link("Read the privacy policy", destination: url)
                    .font(THStyle.ui(15, .semibold)).foregroundStyle(THStyle.goldText)
            }
            Spacer(minLength: 8)
            Button("Allow") { AIConsent.grant(); allowed = true; dismiss() }
                .buttonStyle(THPrimaryButtonStyle())
            Button("Not now") { dismiss() }
                .buttonStyle(THSecondaryButtonStyle())
        }
        .padding(24)
        .background(THStyle.canvas.ignoresSafeArea())
        .presentationDetents([.large])
        .onDisappear {
            // Run after the sheet is gone so the next screen can present cleanly.
            if allowed { onAllow() } else { onDecline() }
        }
    }
}
'''

PATCHES = {
 "ItemIdentifier.swift": [
  ("imports", "import Foundation\nimport SwiftData\nimport FirebaseFunctions\n",
   "import Foundation\nimport SwiftUI\nimport SwiftData\nimport FirebaseFunctions\n"),
  ("outcome", "        case skipped\n    }\n", "        case skipped\n        case needsConsent\n    }\n"),
  ("consent gate", "        guard !inFlight.contains(scan.id) else { return .skipped }\n",
   "        guard !inFlight.contains(scan.id) else { return .skipped }\n"
   "        guard AIConsent.granted else {\n"
   "            ScanRecorder(context: context).setState(.failed, on: scan, error: \"Saved. Allow photo identification to continue.\")\n"
   "            return .needsConsent\n"
   "        }\n"),
  ("retry loop", "            if case .savedForRetry = outcome { break }   // still offline; stop hammering\n",
   "            if case .savedForRetry = outcome { break }   // still offline; stop hammering\n"
   "            if case .needsConsent = outcome { break }\n"),
 ],
 "ScanResultView.swift": [
  ("state", "    @State private var banner: String?\n", "    @State private var banner: String?\n    @State private var showConsent = false\n"),
  ("sheet", "        .sheet(isPresented: $showEditIdentity) { EditIdentitySheet(scan: scan) }\n",
   "        .sheet(isPresented: $showEditIdentity) { EditIdentitySheet(scan: scan) }\n"
   "        .sheet(isPresented: $showConsent) { AIConsentSheet(onAllow: { Task { await identify(force: true) } }) }\n"),
  ("outcome", "        case .skipped:\n            break\n        }\n",
   "        case .skipped:\n            break\n        case .needsConsent:\n            showConsent = true\n        }\n"),
 ],
 "SnapSignView.swift": [
  ("state", "    @State private var publishing = false\n",
   "    @State private var publishing = false\n    @State private var pendingSign: UIImage?\n    @State private var showConsent = false\n"),
  ("sheet", "            .onChange(of: signImage) { _, img in\n",
   "            .sheet(isPresented: $showConsent) {\n"
   "                AIConsentSheet(onAllow: { if let img = pendingSign { parseSign(img) } },\n"
   "                               onDecline: { parseError = \"Reading the sign needs your OK to send the photo. You can still add the sale yourself.\" })\n"
   "            }\n"
   "            .onChange(of: signImage) { _, img in\n"),
  ("gate", "    func parseSign(_ image: UIImage) {\n        parsing = true; parseError = nil\n",
   "    func parseSign(_ image: UIImage) {\n"
   "        guard AIConsent.granted else {\n"
   "            pendingSign = image\n"
   "            // Let the camera sheet finish closing before showing the next one.\n"
   "            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { showConsent = true }\n"
   "            return\n"
   "        }\n"
   "        parsing = true; parseError = nil\n"),
 ],
}

files = {n: find(n) for n in PATCHES}
texts = {n: open(p, encoding="utf-8").read() for n, p in files.items()}
if "AIConsent" in texts["ItemIdentifier.swift"]:
    sys.exit("Already installed. Nothing changed.")
errs = [f"{n}: '{label}' found {texts[n].count(old)} times" for n, ps in PATCHES.items() for label, old, _ in ps if texts[n].count(old) != 1]
if errs: sys.exit("ABORT:\n  " + "\n  ".join(errs) + "\nNothing changed.")
for n, ps in PATCHES.items():
    t = texts[n]
    for _, old, new in ps: t = t.replace(old, new)
    if n == "ItemIdentifier.swift": t = t.rstrip("\n") + SHEET
    shutil.copy2(files[n], files[n] + ".bak-consent")
    open(files[n], "w", encoding="utf-8").write(t)
    print("patched", files[n])
