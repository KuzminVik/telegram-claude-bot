#!/usr/bin/env node

/**
 * MCP Weather Server
 * Предоставляет инструмент для получения погодных данных через Open-Meteo API
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import fetch from "node-fetch";

// Geocoding API для получения координат по названию города
const GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search";
const WEATHER_API = "https://api.open-meteo.com/v1/forecast";

/**
 * Получить координаты города по его названию
 */
async function getCityCoordinates(cityName) {
  const url = `${GEOCODING_API}?name=${encodeURIComponent(cityName)}&count=1&language=ru&format=json`;
  
  try {
    const response = await fetch(url);
    const data = await response.json();
    
    if (!data.results || data.results.length === 0) {
      throw new Error(`Город "${cityName}" не найден`);
    }
    
    const city = data.results[0];
    return {
      name: city.name,
      country: city.country,
      latitude: city.latitude,
      longitude: city.longitude,
      timezone: city.timezone
    };
  } catch (error) {
    throw new Error(`Ошибка при поиске города: ${error.message}`);
  }
}

/**
 * Получить текущую погоду по координатам
 */
async function getCurrentWeather(latitude, longitude, timezone = "auto") {
  const url = `${WEATHER_API}?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m&timezone=${timezone}`;
  
  try {
    const response = await fetch(url);
    const data = await response.json();
    
    if (!data.current) {
      throw new Error("Не удалось получить данные о погоде");
    }
    
    return {
      temperature: data.current.temperature_2m,
      apparent_temperature: data.current.apparent_temperature,
      humidity: data.current.relative_humidity_2m,
      precipitation: data.current.precipitation,
      weather_code: data.current.weather_code,
      wind_speed: data.current.wind_speed_10m,
      wind_direction: data.current.wind_direction_10m,
      time: data.current.time,
      timezone: data.timezone
    };
  } catch (error) {
    throw new Error(`Ошибка при получении погоды: ${error.message}`);
  }
}

/**
 * Преобразовать код погоды WMO в описание
 */
function getWeatherDescription(code) {
  const weatherCodes = {
    0: "Ясно",
    1: "Преимущественно ясно",
    2: "Переменная облачность",
    3: "Пасмурно",
    45: "Туман",
    48: "Изморозь",
    51: "Лёгкая морось",
    53: "Умеренная морось",
    55: "Сильная морось",
    61: "Небольшой дождь",
    63: "Умеренный дождь",
    65: "Сильный дождь",
    71: "Небольшой снег",
    73: "Умеренный снег",
    75: "Сильный снег",
    77: "Снежная крупа",
    80: "Небольшой ливень",
    81: "Умеренный ливень",
    82: "Сильный ливень",
    85: "Небольшой снегопад",
    86: "Сильный снегопад",
    95: "Гроза",
    96: "Гроза с градом",
    99: "Гроза с сильным градом"
  };
  
  return weatherCodes[code] || "Неизвестно";
}

/**
 * Форматировать направление ветра
 */
function getWindDirection(degrees) {
  const directions = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"];
  const index = Math.round(degrees / 45) % 8;
  return directions[index];
}

// Создаём MCP сервер
const server = new Server(
  {
    name: "weather-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Регистрируем список доступных инструментов
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "get_weather",
        description: "Получить текущую погоду для указанного города. Использует Open-Meteo API для получения актуальных данных о температуре, влажности, осадках и ветре.",
        inputSchema: {
          type: "object",
          properties: {
            city: {
              type: "string",
              description: "Название города (на русском или английском). Например: 'Москва', 'Цюрих', 'London'",
            },
          },
          required: ["city"],
        },
      },
    ],
  };
});

// Обработчик вызова инструмента
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name !== "get_weather") {
    throw new Error(`Неизвестный инструмент: ${request.params.name}`);
  }

  const city = request.params.arguments?.city;
  
  if (!city || typeof city !== "string") {
    throw new Error("Параметр 'city' обязателен и должен быть строкой");
  }

  try {
    // Получаем координаты города
    const location = await getCityCoordinates(city);
    
    // Получаем погоду
    const weather = await getCurrentWeather(
      location.latitude,
      location.longitude,
      location.timezone
    );
    
    // Форматируем ответ
    const weatherDescription = getWeatherDescription(weather.weather_code);
    const windDir = getWindDirection(weather.wind_direction);
    
    const response = `🌍 Погода в городе ${location.name}, ${location.country}

🌡️ Температура: ${weather.temperature}°C (ощущается как ${weather.apparent_temperature}°C)
☁️ Состояние: ${weatherDescription}
💧 Влажность: ${weather.humidity}%
🌧️ Осадки: ${weather.precipitation} мм
💨 Ветер: ${weather.wind_speed} км/ч (${windDir})

🕐 Время: ${weather.time}
⏰ Часовой пояс: ${weather.timezone}`;

    return {
      content: [
        {
          type: "text",
          text: response,
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `❌ Ошибка: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Запуск сервера через stdio
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MCP Weather Server запущен на stdio");
}

main().catch((error) => {
  console.error("Фатальная ошибка:", error);
  process.exit(1);
});
