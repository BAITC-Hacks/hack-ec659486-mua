/**
 * Заглушка i18n: словарь ru/kk и функция t(). По умолчанию — русский.
 *
 *   t("loading")        -> "Загрузка…"
 *   t("loading", "kk")  -> "Жүктелуде…"
 *
 * Ключи типизированы по словарю ru; словарь kk обязан содержать те же ключи.
 */

export type Locale = "ru" | "kk";

export const DEFAULT_LOCALE: Locale = "ru";

const ru = {
  loading: "Загрузка…",
  error: "Ошибка",
  retry: "Повторить",
  notFound: "Страница не найдена",
  apiUnavailable: "API недоступен",
  apiOk: "API работает",
  empty: "Пока пусто",
  submit: "Отправить",
  save: "Сохранить",
  cancel: "Отмена",
  back: "Назад",
  home: "На главную",
  search: "Поиск",
  risk: "Риск",
  plan: "План",
} as const;

export type I18nKey = keyof typeof ru;

const kk: Record<I18nKey, string> = {
  loading: "Жүктелуде…",
  error: "Қате",
  retry: "Қайталау",
  notFound: "Бет табылмады",
  apiUnavailable: "API қолжетімсіз",
  apiOk: "API жұмыс істейді",
  empty: "Әзірге бос",
  submit: "Жіберу",
  save: "Сақтау",
  cancel: "Болдырмау",
  back: "Артқа",
  home: "Басты бетке",
  search: "Іздеу",
  risk: "Тәуекел",
  plan: "Жоспар",
};

export const dictionaries: Record<Locale, Record<I18nKey, string>> = { ru, kk };

export function t(key: I18nKey, locale: Locale = DEFAULT_LOCALE): string {
  return dictionaries[locale][key] ?? dictionaries.ru[key] ?? key;
}
