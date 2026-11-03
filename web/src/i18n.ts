/* String dictionary. Add a new language by adding an entry to STRINGS. */

export type Lang = "en" | "pcm";

export interface Strings {
  appName: string;
  appTagline: string;
  desktopNote: string;
  tabs: { scan: string; alerts: string; claims: string; saved: string };

  scanTitle: string;
  fitLabel: string;
  torch: string;
  gallery: string;
  typeInstead: string;
  hintDark: string;
  hintGlare: string;
  hintBlurry: string;
  hintClear: string;
  cameraUnavailableTitle: string;
  cameraUnavailableBody: string;
  retake: string;
  addBatchPhoto: string;
  checkProduct: string;
  photosCount: string;
  sizeNote: string;
  manualTitle: string;
  manualNrnLabel: string;
  manualNrnPlaceholder: string;
  manualNameLabel: string;
  manualNamePlaceholder: string;
  manualExample: string;
  submitManual: string;

  checkingTitle: string;
  stepReading: string;
  stepNumber: string;
  stepGreenbook: string;
  stepNapams: string;
  stepCompare: string;
  stepDone: string;
  stepFailed: string;
  stepSkipped: string;
  retry: string;
  cancel: string;
  timedOut: string;
  queuedNotice: string;
  queuedSending: string;

  resultMatch: string;
  resultDiffers: string;
  resultNotFound: string;
  resultExpired: string;
  resultAlert: string;
  resultKnownTarget: string;
  resultUnreadable: string;
  resultOutage: string;
  outageBody: string;
  alertCardTitle: string;
  alertOpen: string;
  alertDifferences: string;
  alertQuoteLabel: string;
  alertFuzzy: string;
  product: string;
  regNumber: string;
  manufacturer: string;
  category: string;
  status: string;
  expiry: string;
  copy: string;
  copied: string;
  whatChecked: string;
  openSource: string;
  labelVsRegistry: string;
  nameField: string;
  numberField: string;
  makerField: string;
  strengthField: string;
  expiryField: string;
  batchField: string;
  match: string;
  differs: string;
  notAvailable: string;
  ocrConfidence: string;
  editWhatWeRead: string;
  batchCardTitle: string;
  batchUnusual: string;
  batchNotProof: string;
  signalsCardTitle: string;
  signalsNotProof: string;
  signalExpiryPast: string;
  signalExpiryFarFuture: string;
  signalMfgFuture: string;
  signalShelfLifeMismatch: string;
  signalBatchUnusual: string;
  signalBatchConflict: string;
  signalLayoutPrefix: string;
  whyResult: string;
  shareWhatsApp: string;
  reportConcern: string;
  checkAnother: string;
  save: string;
  saved: string;
  disclaimerShort: string;
  howHaskeWorks: string;
  howWorksBody: string;

  alertsTitle: string;
  alertsEmpty: string;
  alertsSearch: string;
  alertsCheckLast: string;
  alertsUpdated: string;

  claimsTitle: string;
  claimsPaste: string;
  claimsCheck: string;
  claimsOfficial: string;
  claimsNotFound: string;
  claimsCantVerify: string;
  claimsSources: string;
  claimsEmpty: string;

  savedTitle: string;
  savedLocalOnly: string;
  savedEmpty: string;
  delete: string;
  deleteAll: string;
  keepPhotos: string;
  deleteConfirm: string;

  settings: string;
  language: string;
  textSize: string;
  clearData: string;
  privacy: string;
  close: string;
  english: string;
  pidgin: string;

  coverageLine: string;
  coverageNapams: string;
  coverageUnavailable: string;

  reasonNrnNotFound: string;
  reasonMismatch: string;
  reasonMatch: string;
  reasonShared: string;
  reasonUnverifiable: string;
  reasonExpired: string;
  reasonUnavailable: string;
  reasonBarcode: string;

  privacyPhoto: string;
  privacyData: string;
  privacyAnalytics: string;

  queuePending: string;
  online: string;
  offline: string;
  installPrompt: string;
  installNow: string;
  installLater: string;
}

const EN: Strings = {
  appName: "Haske",
  appTagline: "Check a NAFDAC number",
  desktopNote: "Open on your phone for the best experience",
  tabs: { scan: "Scan", alerts: "Alerts", claims: "Claims", saved: "Saved" },

  scanTitle: "Scan",
  fitLabel: "Fit the label in the frame",
  torch: "Torch",
  gallery: "Gallery",
  typeInstead: "Type the NAFDAC number instead",
  hintDark: "Too dark. Turn on the torch.",
  hintGlare: "Tilt the pack a little to cut glare.",
  hintBlurry: "Hold steady. The label looks blurry.",
  hintClear: "Label looks clear.",
  cameraUnavailableTitle: "Camera not available",
  cameraUnavailableBody:
    "We could not open your camera. You can still pick a photo from your gallery or type the NAFDAC number.",
  retake: "Retake",
  addBatchPhoto: "Add batch code photo",
  checkProduct: "Check this product",
  photosCount: "photos",
  sizeNote: "sending",
  manualTitle: "Type the number",
  manualNrnLabel: "NAFDAC number",
  manualNrnPlaceholder: "e.g. A4-100160",
  manualNameLabel: "Product name (optional)",
  manualNamePlaceholder: "e.g. Panadol 500mg",
  manualExample: "The number is usually printed near the NAFDAC logo, often as letters and numbers like A4-0123.",
  submitManual: "Check this number",

  checkingTitle: "Checking",
  stepReading: "Reading the label",
  stepNumber: "Found NAFDAC number",
  stepGreenbook: "Checking Greenbook",
  stepNapams: "Checking NAPAMS",
  stepCompare: "Comparing fields",
  stepDone: "Done",
  stepFailed: "didn't respond",
  stepSkipped: "not needed",
  retry: "Retry",
  cancel: "Cancel",
  timedOut: "took too long",
  queuedNotice: "You are offline. We'll check when you're back online.",
  queuedSending: "Back online. Sending your check now.",

  resultMatch: "Matches the registry",
  resultDiffers: "Found, but some details differ",
  resultNotFound: "No matching record found",
  resultExpired: "Registration expired or inactive",
  resultAlert: "Matches an official alert",
  resultKnownTarget: "Known target of an alert",
  resultUnreadable: "We couldn't read the label",
  resultOutage: "The registry didn't respond",
  outageBody: "This does not mean the product is fake. Try again.",
  alertCardTitle: "NAFDAC Public Alert",
  alertOpen: "Open the alert",
  alertDifferences: "What NAFDAC says to look for",
  alertQuoteLabel: "From NAFDAC",
  alertFuzzy: "The batch match was close, so please confirm the batch code carefully.",
  product: "Product",
  regNumber: "Reg. no.",
  manufacturer: "Manufacturer",
  category: "Category",
  status: "Status",
  expiry: "Expiry",
  copy: "Copy",
  copied: "Copied",
  whatChecked: "What we checked",
  openSource: "open source",
  labelVsRegistry: "Label vs registry",
  nameField: "Name",
  numberField: "Number",
  makerField: "Maker",
  strengthField: "Strength",
  expiryField: "Expiry",
  batchField: "Batch code",
  match: "match",
  differs: "differs",
  notAvailable: "not shown",
  ocrConfidence: "Reading confidence",
  editWhatWeRead: "Edit what we read",
  batchCardTitle: "Batch code",
  batchUnusual: "Unusual pattern, not proof",
  batchNotProof:
    "We look for repeated or sequential patterns in the batch code. An unusual pattern is a hint, not proof of anything.",
  signalsCardTitle: "Signals found",
  signalsNotProof:
    "These signals were found on the label. They are worth noting but are not proof of anything on their own.",
  signalExpiryPast: "Expiry date is in the past.",
  signalExpiryFarFuture: "Expiry date is unusually far in the future.",
  signalMfgFuture: "Manufacture date is in the future.",
  signalShelfLifeMismatch: "Stated shelf life does not match the gap between manufacture and expiry dates.",
  signalBatchUnusual: "Batch code has an unusual repeated or sequential pattern.",
  signalBatchConflict: "The expiry date on this label differs from other scans of the same batch code.",
  signalLayoutPrefix: "Label signal",
  whyResult: "Why this result",
  shareWhatsApp: "Share on WhatsApp",
  reportConcern: "Report a concern",
  checkAnother: "Check another",
  save: "Save",
  saved: "Saved",
  disclaimerShort: "A match means the label agrees with the registry. It does not prove the product is genuine.",
  howHaskeWorks: "How Haske works",
  howWorksBody:
    "Haske reads the label on your product, finds the NAFDAC registration number, and checks it against the official Greenbook and NAPAMS registries. A match means the label agrees with the registry. It does not prove the product is genuine. If a registry does not answer, we say so rather than guess. Verdicts come from the registry data, never from a guess by a model.",

  alertsTitle: "Alerts",
  alertsEmpty: "No public NAFDAC alerts right now. We'll show recalls and advisories here when they are published.",
  alertsSearch: "Search alerts",
  alertsCheckLast: "Check my last product against alerts",
  alertsUpdated: "Last updated",

  claimsTitle: "Claims",
  claimsPaste: "Paste or share in a forwarded message",
  claimsCheck: "Check this claim",
  claimsOfficial: "Matches an official notice",
  claimsNotFound: "Not found in official sources",
  claimsCantVerify: "Can't verify",
  claimsSources: "Sources we searched",
  claimsEmpty: "Paste a message you received to check it against official sources.",

  savedTitle: "Saved",
  savedLocalOnly: "Saved on this phone only.",
  savedEmpty: "No saved checks yet. Scan a product and tap Save.",
  delete: "Delete",
  deleteAll: "Delete all",
  keepPhotos: "Keep photos on this phone",
  deleteConfirm: "Delete all saved checks?",

  settings: "Settings",
  language: "Language",
  textSize: "Text size",
  clearData: "Clear data",
  privacy: "Privacy",
  close: "Close",
  english: "English",
  pidgin: "Nigerian Pidgin",

  coverageLine: "Checks {n} records from NAFDAC Greenbook",
  coverageNapams: "NAPAMS checked live",
  coverageUnavailable: "Coverage details unavailable right now",

  reasonNrnNotFound: "The registration number was not found in the register.",
  reasonMismatch: "The number exists, but the register shows it belongs to a different product.",
  reasonMatch: "The label agrees with the register. This does not prove the product is genuine.",
  reasonShared: "The number is shared by more than one product, so we cannot confirm which one it is.",
  reasonUnverifiable: "The number exists, but there is not enough label detail to confirm the product.",
  reasonExpired: "The register shows this registration is expired or inactive.",
  reasonUnavailable: "The register could not be checked, so there is no verdict either way.",
  reasonBarcode: "That looks like a barcode, not a NAFDAC number.",

  privacyPhoto:
    "Your photo is processed on our server to read the label, then discarded. We do not keep your photos or create accounts.",
  privacyData: "Saved results are stored only on this phone. We do not keep your email, phone, or address.",
  privacyAnalytics: "No ads and no tracking scripts. We count checks and latency only, never who made them.",

  queuePending: "Waiting to send",
  online: "Online",
  offline: "Offline",
  installPrompt: "Add Haske to your home screen for faster checks.",
  installNow: "Install",
  installLater: "Not now",
};

/* Nigerian Pidgin. Core strings translated; anything missing falls back to English. */
const PCM: Strings = {
  ...EN,
  appTagline: "Check NAFDAC number",
  desktopNote: "Open am for your phone make e better",
  tabs: { scan: "Scan", alerts: "Alerts", claims: "Claims", saved: "Saved" },

  scanTitle: "Scan",
  fitLabel: "Put the label inside the frame",
  torch: "Torch",
  gallery: "Gallery",
  typeInstead: "Type the NAFDAC number instead",
  hintDark: "E too dark. On the torch.",
  hintBlurry: "Hold am well. The label no clear.",
  hintClear: "Label clear.",
  cameraUnavailableTitle: "Camera no dey",
  cameraUnavailableBody: "We no fit open your camera. You fit pick photo from gallery or type the number.",
  retake: "Take again",
  addBatchPhoto: "Add batch code photo",
  checkProduct: "Check this product",
  manualTitle: "Type the number",
  manualNrnLabel: "NAFDAC number",
  manualNameLabel: "Product name (no be compulsory)",
  submitManual: "Check this number",

  checkingTitle: "Checking",
  stepReading: "Reading the label",
  stepNumber: "Done see NAFDAC number",
  stepGreenbook: "Checking Greenbook",
  stepNapams: "Checking NAPAMS",
  stepCompare: "Comparing the things",
  stepFailed: "no gree answer",
  retry: "Try again",
  cancel: "Cancel",
  queuedNotice: "You no get network. We go check am when network return.",

  resultMatch: "E match the registry",
  resultDiffers: "E dey, but some details no match",
  resultNotFound: "We no see matching record",
  resultExpired: "Registration don expire",
  resultAlert: "E match official alert",
  resultKnownTarget: "Dem know this product before",
  resultUnreadable: "We no fit read the label",
  resultOutage: "The registry no gree answer",
  outageBody: "This one no mean say the product be fake. Try again.",
  alertCardTitle: "NAFDAC Public Alert",
  alertOpen: "Open the alert",
  alertDifferences: "Wetin NAFDAC talk say make we look for",
  alertQuoteLabel: "From NAFDAC",
  alertFuzzy: "The batch match near, so check the batch code well.",
  product: "Product",
  regNumber: "Reg. no.",
  manufacturer: "Manufacturer",
  category: "Category",
  status: "Status",
  expiry: "Expiry",
  copy: "Copy",
  copied: "Don copy",
  whatChecked: "Wetin we check",
  openSource: "open source",
  labelVsRegistry: "Label vs registry",
  nameField: "Name",
  numberField: "Number",
  makerField: "Maker",
  expiryField: "Expiry",
  batchField: "Batch code",
  match: "match",
  differs: "no match",
  whyResult: "Why this result",
  shareWhatsApp: "Share for WhatsApp",
  reportConcern: "Report wahala",
  checkAnother: "Check another one",
  save: "Save",
  saved: "Done save",
  disclaimerShort: "If e match, na say label and registry agree. E no mean say the product be original.",

  signalsCardTitle: "Signals we see",
  signalsNotProof:
    "These signals dey for the label. Dem worth noting but no be proof of anything.",
  signalExpiryPast: "Expiry date don pass.",
  signalExpiryFarFuture: "Expiry date too far for front.",
  signalMfgFuture: "Manufacture date dey for future.",
  signalShelfLifeMismatch: "Shelf life no match the dates wey dem print.",
  signalBatchUnusual: "Batch code get unusual pattern.",
  signalBatchConflict: "The expiry date no match other scans of same batch.",

  alertsTitle: "Alerts",
  alertsEmpty: "No public NAFDAC alert for now. We go show recalls and warnings here when dem publish.",
  claimsTitle: "Claims",
  savedTitle: "Saved",
  savedLocalOnly: "E dey for this phone only.",
  savedEmpty: "You never save any check. Scan product then tap Save.",
  delete: "Comot",
  deleteAll: "Comot all",
  settings: "Settings",
  language: "Language",
  textSize: "Text size",
  clearData: "Clear data",
  privacy: "Privacy",
  close: "Close",
  english: "English",
  pidgin: "Nigerian Pidgin",
  installPrompt: "Put Haske for your home screen make checking fast.",
  installNow: "Install",
  installLater: "No now",
};

export const STRINGS: Record<Lang, Strings> = { en: EN, pcm: PCM };
