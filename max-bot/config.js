import dotenv from 'dotenv';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Поиск .env файла в нескольких возможных местах
const envCandidates = [
  path.resolve(__dirname, '.env'),
  path.resolve(__dirname, '..', '.env'),
  path.resolve(__dirname, '..', 'xray-be', '.env'),
];

for (const candidate of envCandidates) {
  if (fs.existsSync(candidate)) {
    dotenv.config({ path: candidate });
    break;
  }
}

// Отключение строгой проверки самоподписанных / региональных сертификатов Минцифры,
// если не заданы кастомные сертификаты CA
if (!process.env.NODE_EXTRA_CA_CERTS) {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
}

export const config = {
  MAX_BOT_TOKEN: process.env.MAX_BOT_TOKEN || 'f9LHodD0cOJBhxITwPCdJEVxZ7O2jzj6oDVpd_ODgTheRYaSUX8ErQbLWGisLOw5-U9xswXPu-vQfO0yAcCT',
  MAX_BOT_USERNAME: process.env.MAX_BOT_USERNAME || 'se14421867_bot',
  MAX_APP_URL: (process.env.MAX_APP_URL || 'https://xray-business-bot.online').replace(/\/+$/, ''),
  MAX_API_BASE_URL: process.env.MAX_API_BASE_URL || 'https://platform-api2.max.ru',
  PORT: parseInt(process.env.PORT || '3000', 10),
  WEBHOOK_URL: process.env.WEBHOOK_URL || '',
};
