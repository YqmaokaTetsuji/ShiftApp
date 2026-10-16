// スプレッドシート側（Google Apps Script）。
// Apps Script エディタにこの内容を貼り付け、「デプロイを管理」から
// 既存のウェブアプリのデプロイを「新しいバージョン」に更新してください。

var REQUEST_LOG_SHEET = '_提出ID';  // 重複排除の記録用。非表示シート
var LOCK_TIMEOUT_MS = 20000;

// スマホからのシフト提出を受け取る機能（文字列強制保存モード＋二重登録の防止）
function doPost(e) {
  // 同時に届いた提出どうしで「重複チェック → 書き込み」がすれ違わないように直列化する
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_TIMEOUT_MS)) {
    return jsonOutput_({"status": "error", "message": "混み合っています。少し待ってから再度お試しください。"});
  }

  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var data = JSON.parse(e.postData.contents);

    // 重複排除用の ID は行には書かない。シートの列構成を従来どおりに保つため
    // （Excel 出力や店長パネルは列名をそのまま見ている）
    var requestId = data["request_id"] || "";
    delete data["request_id"];

    // 同じ内容がすでに保存済みなら、成功として返して何もしない。
    // 連打・通信リトライ・リロード後の再提出は、すべてここで止まる。
    if (requestId && isDuplicateRequest_(ss, requestId)) {
      return jsonOutput_({"status": "success", "duplicate": true});
    }

    // 対象月は「2026年01月」形式で届くので、シート名は「2026年01月シフト」になる
    var sheetName = data["対象月"] + "シフト";
    var sheet = ss.getSheetByName(sheetName);

    var headers = Object.keys(data);
    var rowData = Object.values(data);

    // もしその月のシートがなければ新しく作って1行目に見出しを入れる
    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
      writeHeaders_(sheet, headers);
    } else if (sheet.getLastRow() === 0) {
      writeHeaders_(sheet, headers);
    }

    // 次の行のセルの書式を「文字列（@）」に指定してから保存する
    var nextRow = sheet.getLastRow() + 1;
    var dataRange = sheet.getRange(nextRow, 1, 1, rowData.length);
    dataRange.setNumberFormat('@'); // これで「10-19」が日付に変換されなくなる
    dataRange.setValues([rowData]);
    SpreadsheetApp.flush();

    // 行を書き終えてから ID を記録する。逆順にすると、書き込みに失敗したときに
    // 「ID だけ残って、正しい再提出が重複として捨てられる」ことになってしまう
    if (requestId) {
      recordRequestId_(ss, requestId, sheetName, data["従業員コード"], data["名前"]);
    }

    return jsonOutput_({"status": "success"});
  } catch(error) {
    return jsonOutput_({"status": "error", "message": error.toString()});
  } finally {
    lock.releaseLock();
  }
}

function writeHeaders_(sheet, headers) {
  var headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setNumberFormat('@'); // 見出しもテキスト形式に指定
  headerRange.setValues([headers]);
}

function getRequestLogSheet_(ss) {
  var sheet = ss.getSheetByName(REQUEST_LOG_SHEET);
  if (!sheet) {
    sheet = ss.insertSheet(REQUEST_LOG_SHEET);
    sheet.getRange(1, 1, 1, 5)
      .setNumberFormat('@')
      .setValues([["request_id", "受付日時", "保存先シート", "従業員コード", "名前"]]);
    sheet.hideSheet();
  }
  return sheet;
}

function isDuplicateRequest_(ss, requestId) {
  var sheet = getRequestLogSheet_(ss);
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    return false;
  }
  var ids = sheet.getRange(2, 1, lastRow - 1, 1).getDisplayValues();
  for (var i = 0; i < ids.length; i++) {
    if (ids[i][0] === requestId) {
      return true;
    }
  }
  return false;
}

function recordRequestId_(ss, requestId, sheetName, code, name) {
  var sheet = getRequestLogSheet_(ss);
  var row = sheet.getLastRow() + 1;
  var stamp = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm:ss");
  sheet.getRange(row, 1, 1, 5)
    .setNumberFormat('@')
    .setValues([[requestId, stamp, sheetName, code || "", name || ""]]);
}

function jsonOutput_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// 店長パネルの読み取り機能（見た目通りの文字列をそのまま取り出すモード）
function doGet(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var reqType = e.parameter.type;

  // 名簿を取得する場合
  if (reqType === "member") {
    var sheet = ss.getSheetByName("名簿");
    if (!sheet) {
      return jsonOutput_([]);
    }
    // getDisplayValues() を使うと、セルで見えているままの文字を取り出せる
    return jsonOutput_(sheet.getDataRange().getDisplayValues());
  }
  // シフトデータを取得する場合
  else {
    // month は「2026年01月」形式（提出時の「対象月」と同じ表記）
    var targetMonth = e.parameter.month;
    var sheetName = targetMonth + "シフト";
    var sheet = ss.getSheetByName(sheetName);

    if (!sheet) {
      return jsonOutput_([]);
    }

    // こちらも見えているままの文字列で Excel 等に渡す
    return jsonOutput_(sheet.getDataRange().getDisplayValues());
  }
}

// ---- 古い月のシフトシートの自動削除 ----
// 当月と前月のシートだけ残し、それより前の「YYYY年MM月シフト」を削除する。
// 例：11月1日に動くと 9月以前のシートが消え、10月・11月（と先の月）は残る。
// 「名簿」「_提出ID」など、名前が「YYYY年MM月シフト」でないシートには触らない。
var KEEP_PAST_MONTHS = 1;  // 当月に加えて残す過去の月数
var CLEANUP_HANDLER = "deleteOldShiftSheets";

function deleteOldShiftSheets() {
  // 提出の書き込みとすれ違わないよう、doPost と同じロックを取る
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_TIMEOUT_MS)) {
    throw new Error("ロックを取得できなかったため、古いシートの削除を見送りました。");
  }

  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    // スクリプトのタイムゾーン設定に左右されないよう、日本時間で今月を決める
    var now = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM").split("-");
    var oldestKept = Number(now[0]) * 12 + (Number(now[1]) - 1) - KEEP_PAST_MONTHS;

    var deleted = [];
    ss.getSheets().forEach(function(sheet) {
      var m = sheet.getName().match(/^(\d{4})年(\d{2})月シフト$/);
      if (m && Number(m[1]) * 12 + (Number(m[2]) - 1) < oldestKept) {
        deleted.push(sheet.getName());
        ss.deleteSheet(sheet);
      }
    });

    if (deleted.length > 0) {
      pruneRequestLog_(ss, deleted);
    }
    console.log("削除したシート: " + (deleted.length > 0 ? deleted.join(", ") : "なし"));
  } finally {
    lock.releaseLock();
  }
}

// 消したシート宛ての提出 ID も _提出ID から取り除く（記録が際限なく増えないように）
function pruneRequestLog_(ss, deletedSheetNames) {
  var sheet = ss.getSheetByName(REQUEST_LOG_SHEET);
  if (!sheet || sheet.getLastRow() < 2) {
    return;
  }
  var rows = sheet.getRange(2, 1, sheet.getLastRow() - 1, 5).getDisplayValues();
  var kept = rows.filter(function(row) {
    return deletedSheetNames.indexOf(row[2]) === -1;
  });
  if (kept.length === rows.length) {
    return;
  }
  sheet.getRange(2, 1, rows.length, 5).clearContent();
  if (kept.length > 0) {
    sheet.getRange(2, 1, kept.length, 5).setNumberFormat('@').setValues(kept);
  }
}

// 最初に一度だけ、Apps Script エディタからこの関数を選んで実行する。
// 毎月1日の0時台（スクリプトのタイムゾーン基準）に deleteOldShiftSheets が動くようになる。
// 何度実行しても、トリガーは1つだけになる。
function installCleanupTrigger() {
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (trigger.getHandlerFunction() === CLEANUP_HANDLER) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger(CLEANUP_HANDLER)
    .timeBased()
    .onMonthDay(1)
    .atHour(0)
    .create();
}
