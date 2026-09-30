import { Bot, Keyboard } from '@maxhub/max-bot-api';
import { config } from './config.js';

/**
 * Создает и настраивает экземпляр чат-бота для мессенджера MAX.
 *
 * Обрабатывает:
 * - Событие "Старт" (bot_started) — когда пользователь начинает диалог в мессенджере
 * - Команду /start — прямой запуск через команду
 * - Команду /help — справку о возможностях сервиса
 * - Входящие текстовые сообщения — перенаправление в Mini App
 * - Добавление бота в групповой чат (bot_added)
 */
export function createBot(token = config.MAX_BOT_TOKEN) {
  if (!token) {
    throw new Error('Токен бота MAX_BOT_TOKEN не задан!');
  }

  const bot = new Bot(token);

  /**
   * Формирует клавиатуру с кнопками для перехода в Mini App:
   * 1. open_app: открывает мини-приложение встроенным WebView внутри MAX
   * 2. link: универсальная ссылка на мини-приложение в MAX
   * 3. link: прямая веб-ссылка на веб-версию сервиса
   */
  function getWelcomeKeyboard() {
    return Keyboard.inlineKeyboard([
      [
        Keyboard.button.openApp('🚀 Открыть мини-приложение', config.MAX_BOT_USERNAME),
      ],
      [
        Keyboard.button.link('🌐 Веб-версия', config.MAX_APP_URL),
      ],
    ]);
  }

  /**
   * Приветственный текст сообщения с описанием возможностей X-Ray Business
   */
  function getWelcomeMessage(userName = '') {
    const greeting = userName ? `👋 Привет, ${userName}!` : '👋 Привет!';
    return `${greeting}

Добро пожаловать в X-Ray Business — интеллектуальную систему экспресс-диагностики и аудита B2B-продаж для платформы MAX.

🔍 Что умеет сервис:
• ⚡ Мгновенный анализ воронки продаж и конверсий по этапам
• 🛑 Поиск узких мест, «зависших» сделок и аномалий
• 💰 Расчет скрытых потерь выручки (Lost Revenue)
• 🤖 AI-диагноз и персонализированные рекомендации по росту продаж
• 📥 Интеграция с CRM (AmoCRM, Bitrix24, МойСклад) и загрузка Excel/CSV

🚀 Чтобы начать работу, нажмите на кнопку ниже и перейдите в мини-приложение
Если мини-приложение бесконечно загружается, откройте веб-версию (без аутентификации через MAX история удаляется через 24 часа)`;
  }

  // 1. Событие нажатия кнопки "Старт" в интерфейсе MAX (начало работы с ботом)
  bot.on('bot_started', async (ctx) => {
    try {
      const name = ctx.user?.first_name || '';
      console.log(`[BOT] Событие 'bot_started' от пользователя ${ctx.user?.user_id} (${name}) в чате ${ctx.chatId}`);
      await ctx.reply(getWelcomeMessage(name), {
        attachments: [getWelcomeKeyboard()],
      });
    } catch (err) {
      console.error('[BOT ERROR] Ошибка при обработке bot_started:', err);
    }
  });

  // 2. Команда /start (если пользователь ввел текстом или выбрал из меню)
  bot.command('start', async (ctx) => {
    try {
      const name = ctx.user?.first_name || '';
      console.log(`[BOT] Команда /start от пользователя ${ctx.user?.user_id} (${name}) в чате ${ctx.chatId}`);
      await ctx.reply(getWelcomeMessage(name), {
        attachments: [getWelcomeKeyboard()],
      });
    } catch (err) {
      console.error('[BOT ERROR] Ошибка при обработке /start:', err);
    }
  });

  // 3. Команда /help (справка)
  bot.command('help', async (ctx) => {
    try {
      console.log(`[BOT] Команда /help от пользователя ${ctx.user?.user_id} в чате ${ctx.chatId}`);
      const helpText = `ℹ️ **Справка по X-Ray Business**

X-Ray Business — это сервис для экспресс-аудита воронки продаж и поиска скрытых потерь выручки.

Все функции доступны прямо в нашем мини-приложении:
1. Загрузите выгрузку сделок (.csv или .xlsx) или выберите демо-данные
2. Подключите вашу CRM (AmoCRM, Bitrix24, МойСклад) в 1 клик
3. Получите интерактивную аналитику, метрики и персональные советы AI-ассистента

Нажмите кнопку ниже, чтобы открыть мини-приложение:`;
      await ctx.reply(helpText, {
        attachments: [getWelcomeKeyboard()],
      });
    } catch (err) {
      console.error('[BOT ERROR] Ошибка при обработке /help:', err);
    }
  });

  // 4. Любое текстовое сообщение от пользователя
  bot.on('message_created', async (ctx) => {
    try {
      const text = ctx.message?.body?.text?.trim() || '';
      if (text.startsWith('/start') || text.startsWith('/help')) {
        return;
      }
      const name = ctx.user?.first_name || '';
      console.log(`[BOT] Входящее сообщение от ${ctx.user?.user_id} (${name}): "${text}"`);
      const replyText = `👋 ${name ? name + ', я' : 'Я'} бот-ассистент сервиса X-Ray Business.

Вся аналитика, аудит воронки продаж и чат со встроенным AI-консультантом работают в нашем мини-приложении.

Нажмите кнопку ниже, чтобы открыть приложение:`;
      await ctx.reply(replyText, {
        attachments: [getWelcomeKeyboard()],
      });
    } catch (err) {
      console.error('[BOT ERROR] Ошибка при обработке message_created:', err);
    }
  });

  // 5. Бот добавлен в групповой чат
  bot.on('bot_added', async (ctx) => {
    try {
      console.log(`[BOT] Бот добавлен в чат ${ctx.chatId}`);
      await ctx.reply(
        '👋 Всем привет! Я бот X-Ray Business. Я помогаю находить скрытые потери выручки в воронках продаж. Нажмите кнопку, чтобы запустить аудит:',
        { attachments: [getWelcomeKeyboard()] }
      );
    } catch (err) {
      console.error('[BOT ERROR] Ошибка при обработке bot_added:', err);
    }
  });

  // Глобальный перехват ошибок
  bot.catch((err, ctx) => {
    console.error(`[BOT ERROR] Необработанная ошибка (${ctx?.updateType || 'unknown'}):`, err);
  });

  return bot;
}
