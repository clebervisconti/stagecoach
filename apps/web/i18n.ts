import {hasLocale} from 'next-intl';
import {getRequestConfig} from 'next-intl/server';

export const locales = ['en', 'pt-BR'] as const;
export type Locale = (typeof locales)[number];

export default getRequestConfig(async ({requestLocale}) => {
  const requested = await requestLocale;
  const locale = hasLocale(locales, requested) ? requested : 'en';

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
