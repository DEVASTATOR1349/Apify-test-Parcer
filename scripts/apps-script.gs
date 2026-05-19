/**
 * Парсер подписчиков — Google Apps Script Web App
 * Принимает POST через doPost(), раскладывает по листам.
 *
 * Поддерживаемые типы запросов:
 *   "batch_write"     — запись массива строк в несколько листов
 *   "batch_errors"    — запись массива ошибок в лист Ошибки
 *   "error"           — одиночная ошибка (для обратной совместимости)
 *   "write"           — одиночная запись (для обратной совместимости)
 */

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const type = data.type;

    switch (type) {
      case "batch_write":
        return handleBatchWrite(data);
      case "batch_errors":
        return handleBatchErrors(data);
      case "error":
        return handleSingleError(data);
      case "write":
        return handleSingleWrite(data);
      default:
        return ContentService.createTextOutput("UNKNOWN_TYPE: " + type);
    }
  } catch (err) {
    return ContentService.createTextOutput("ERROR: " + err.message);
  }
}


// ──────────────────────────────────────────────────
//  Батч-запись в несколько листов
// ──────────────────────────────────────────────────
function handleBatchWrite(data) {
  const tabs = data.tabs;   // ["Статистика (raw)", "Статистика"]
  const rows = data.rows;   // [[date, client, platform, followers], ...]

  if (!rows || rows.length === 0) {
    return ContentService.createTextOutput("OK");  // нечего писать
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();

  for (const tabName of tabs) {
    let sheet = ss.getSheetByName(tabName);
    if (!sheet) {
      sheet = ss.insertSheet(tabName);
      sheet.appendRow(["Дата", "Клиент", "Площадка", "Подписчиков"]);
    }

    // Пишем всё одним вызовом (не построчно!)
    const lastRow = sheet.getLastRow();
    const range = sheet.getRange(lastRow + 1, 1, rows.length, 4);
    range.setValues(rows);
  }

  return ContentService.createTextOutput("OK");
}


// ──────────────────────────────────────────────────
//  Батч-запись ошибок
// ──────────────────────────────────────────────────
function handleBatchErrors(data) {
  const tab = data.tab || "Ошибки";
  const rows = data.rows;  // [[date, client, link, error], ...]

  if (!rows || rows.length === 0) {
    return ContentService.createTextOutput("OK");
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(tab);
  if (!sheet) {
    sheet = ss.insertSheet(tab);
    sheet.appendRow(["Дата", "Клиент", "Ссылка", "Ошибка"]);
  }

  const lastRow = sheet.getLastRow();
  const range = sheet.getRange(lastRow + 1, 1, rows.length, 4);
  range.setValues(rows);

  return ContentService.createTextOutput("OK");
}


// ──────────────────────────────────────────────────
//  Одиночные — обратная совместимость
// ──────────────────────────────────────────────────
function handleSingleWrite(data) {
  const { tab, date, client, platform, followers } = data;

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(tab);
  if (!sheet) {
    sheet = ss.insertSheet(tab);
    sheet.appendRow(["Дата", "Клиент", "Площадка", "Подписчиков"]);
  }

  sheet.appendRow([date, client, platform, followers]);
  return ContentService.createTextOutput("OK");
}


function handleSingleError(data) {
  const { date, client, link, error } = data;
  const tab = "Ошибки";

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(tab);
  if (!sheet) {
    sheet = ss.insertSheet(tab);
    sheet.appendRow(["Дата", "Клиент", "Ссылка", "Ошибка"]);
  }

  sheet.appendRow([date, client, link, error]);
  return ContentService.createTextOutput("OK");
}
