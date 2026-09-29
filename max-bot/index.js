import { config } from './config.js';
import { createBot } from './bot.js';

async function main() {
  console.log('====================================================');
  console.log('🚀 Запуск MAX Bot для X-Ray Business...');
  console.log('====================================================');

  const bot = createBot(config.MAX_BOT_TOKEN);

  try {
    const info = await bot.api.getMyInfo();
    console.log(`✅ Бот успешно авторизован в MAX API:`);
    console.log(`   - ID: ${info.user_id}`);
    console.log(`   - Имя: ${info.first_name || info.name}`);
    console.log(`   - Username: @${info.username}`);
    console.log(`   - Mini App deep link: https://max.ru/${info.username}?startapp`);
    console.log(`   - Web App URL: ${config.MAX_APP_URL}`);

    // Регистрация команд бота в интерфейсе мессенджера
    try {
      await bot.api.setMyCommands([
        { name: 'start', description: 'Открыть мини-приложение X-Ray' },
        { name: 'help', description: 'Справка о возможностях сервиса' },
      ]);
      console.log('✅ Команды меню /start и /help зарегистрированы в MAX');
    } catch (cmdErr) {
      console.warn('⚠️ Предупреждение: не удалось зарегистрировать команды:', cmdErr?.message || cmdErr);
    }

    // Режим работы: Webhook или Long Polling
    if (config.WEBHOOK_URL) {
      console.log(`📡 Запуск в режиме Webhook на URL: ${config.WEBHOOK_URL}`);
      await bot.start({
        mode: 'webhook',
        options: {
          url: config.WEBHOOK_URL,
          port: config.PORT,
        },
      });
      console.log(`✅ Webhook сервер слушает порт ${config.PORT}`);
    } else {
      console.log('🔄 Запуск в режиме Long Polling (ожидание событий /start и bot_started)...');
      await bot.start({
        mode: 'polling',
        options: {
          retry: true,
        },
      });
    }

    // Корректное завершение при SIGINT/SIGTERM
    const shutdown = async () => {
      console.log('\n🛑 Остановка MAX Bot...');
      try {
        bot.stopPolling();
      } catch {}
      process.exit(0);
    };

    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);

  } catch (error) {
    console.error('❌ Критическая ошибка при запуске бота:', error);
    process.exit(1);
  }
}

main();
