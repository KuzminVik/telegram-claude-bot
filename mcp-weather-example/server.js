#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import fetch from 'node-fetch';

const server = new Server(
  {
    name: 'weather-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

const WEATHER_CONDITIONS = {
  0: 'Ясно',
  1: 'Преимущественно ясно',
  2: 'Переменная облачность',
  3: 'Пасмурно',
  45: 'Туман',
  48: 'Изморозь',
  51: 'Лёгкая морось',
  53: 'Умеренная морось',
  55: 'Сильная морось',
  61: 'Небольшой дождь',
  63: 'Умеренный дождь',
  65: 'Сильный дождь',
  71: 'Небольшой снег',
  73: 'Умеренный снег',
  75: 'Сильный снег',
  77: 'Снежная крупа',
  80: 'Небольшие ливни',
  81: 'Умеренные ливни',
  82: 'Сильные ливни',
  85: 'Небольшие снежные дожди',
  86: 'Сильные снежные дожди',
  95: 'Гроза',
  96: 'Гроза с градом',
  99: 'Гроза с сильным градом'
};

function getWindDirection(degrees) {
  const directions = ['С', 'ССВ', 'СВ', 'ВСВ', 'В', 'ВЮВ', 'ЮВ', 'ЮЮВ', 'Ю', 'ЮЮЗ', 'ЮЗ', 'ЗЮЗ', 'З', 'ЗСЗ', 'СЗ', 'ССЗ'];
  const index = Math.round(degrees / 22.5) % 16;
  return directions[index];
}

async function getWeather(city, includeForecast = false) {
  try {
    const geocodingUrl = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1&language=ru&format=json`;
    
    const geoResponse = await fetch(geocodingUrl);
    const geoData = await geoResponse.json();
    
    if (!geoData.results || geoData.results.length === 0) {
      return { error: `Город "${city}" не найден` };
    }
    
    const location = geoData.results[0];
    const { latitude, longitude, name, country, timezone } = location;
    
    // Базовый URL с текущей погодой
    let weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m&timezone=${timezone}`;
    
    // Если нужен прогноз - добавляем daily параметры
    if (includeForecast) {
      weatherUrl += '&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset';
    }
    
    const weatherResponse = await fetch(weatherUrl);
    const weatherData = await weatherResponse.json();
    
    const current = weatherData.current;
    const condition = WEATHER_CONDITIONS[current.weather_code] || 'Неизвестно';
    const windDir = getWindDirection(current.wind_direction_10m);
    
    let weatherInfo = `🌍 Погода в городе ${name}, ${country}

🌡️ Температура: ${current.temperature_2m}°C (ощущается как ${current.apparent_temperature}°C)
☁️ Состояние: ${condition}
💧 Влажность: ${current.relative_humidity_2m}%
🌧️ Осадки: ${current.precipitation} мм
💨 Ветер: ${Math.round(current.wind_speed_10m)} км/ч (${windDir})

🕐 Время: ${current.time}
⏰ Часовой пояс: ${timezone}`;

    const result = { weather_info: weatherInfo };
    
    // Добавляем прогноз если запрошен
    if (includeForecast && weatherData.daily) {
      const daily = weatherData.daily;
      result.forecast = {
        temp_max: daily.temperature_2m_max[0],
        temp_min: daily.temperature_2m_min[0],
        precipitation_probability: daily.precipitation_probability_max[0] || 0,
        sunrise: daily.sunrise[0],
        sunset: daily.sunset[0]
      };
    }

    return result;
    
  } catch (error) {
    return { error: `Ошибка получения погоды: ${error.message}` };
  }
}

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'get_weather',
      description: 'Получить текущую погоду и опционально прогноз на день для указанного города',
      inputSchema: {
        type: 'object',
        properties: {
          city: {
            type: 'string',
            description: 'Название города',
          },
          include_forecast: {
            type: 'boolean',
            description: 'Включить прогноз на сегодняшний день (макс/мин температура, осадки, восход/закат)',
            default: false
          }
        },
        required: ['city'],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === 'get_weather') {
    const city = request.params.arguments.city;
    const includeForecast = request.params.arguments.include_forecast || false;
    const result = await getWeather(city, includeForecast);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result),
        },
      ],
    };
  }
  
  throw new Error(`Unknown tool: ${request.params.name}`);
});

async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('MCP Weather Server запущен на stdio');
}

runServer().catch(console.error);
