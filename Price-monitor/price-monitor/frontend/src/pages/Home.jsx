import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  BarChart3, Search, TrendingUp, Clock, Shield, Zap,
  Globe, MousePointerClick, Database, Download, Smartphone,
  ChevronRight, ArrowRight, CheckCircle2,
  Store, ShoppingBag, Users
} from 'lucide-react'

export default function Home() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const handleDemoClick = () => {
    navigate('/dashboard', { state: { demo: true } })
  }

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-blue-50 via-primary-50 to-primary-100 dark:from-gray-900 dark:via-primary-900 dark:to-primary-800">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PHBhdGggZD0iTTM2IDM0djItSDI0di0yaDEyek0zNiAyNHYySDI0di0yaDEyeiIvPjwvZz48L2c+PC9zdmc+')] opacity-40 dark:opacity-30"></div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 lg:py-32">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center px-3 py-1 rounded-full bg-primary-100 dark:bg-white/10 text-primary-700 dark:text-primary-200 text-sm mb-6 border border-primary-200 dark:border-white/10">
                <Zap className="h-3.5 w-3.5 mr-2" />
                Автоматический мониторинг цен конкурентов
              </div>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6 leading-tight text-gray-900 dark:text-white">
                Анализируйте цены
                <span className="text-primary-600 dark:text-primary-300"> конкурентов</span> без лишней работы
              </h1>
              <p className="text-lg sm:text-xl text-gray-600 dark:text-primary-100 mb-8 max-w-2xl leading-relaxed">
                Добавьте конкурентов вручную — <br />
                PriceMonitor оперативно соберёт актуальные цены и наглядно сравнит их с вашими.
              </p>
              <div className="flex flex-col sm:flex-row gap-4">
                {!user && (
                  <button
                    onClick={handleDemoClick}
                    className="inline-flex items-center justify-center bg-primary-600 text-white px-8 py-3.5 rounded-xl font-semibold hover:bg-primary-700 transition-all shadow-lg shadow-primary-900/20 group"
                  >
                    Демо-режим
                    <ArrowRight className="h-4 w-4 ml-2 group-hover:translate-x-1 transition-transform" />
                  </button>
                )}
                <Link
                  to="/login"
                  className="inline-flex items-center justify-center border-2 border-primary-300 dark:border-white/30 text-primary-700 dark:text-white px-8 py-3.5 rounded-xl font-semibold hover:bg-primary-50 dark:hover:bg-white/10 transition-colors"
                >
                  Войти
                </Link>
              </div>
            </div>
            <div className="hidden lg:flex justify-center">
              <div className="relative">
                <div className="w-80 h-80 rounded-2xl bg-white/60 dark:bg-gradient-to-br dark:from-primary-400/30 dark:to-primary-600/30 border border-primary-200 dark:border-white/10 backdrop-blur-sm p-6 flex items-center justify-center">
                  <div className="space-y-4 w-full">
                    <div className="h-3 bg-primary-200 dark:bg-white/20 rounded-full w-3/4"></div>
                    <div className="h-3 bg-primary-200 dark:bg-white/20 rounded-full w-1/2"></div>
                    <div className="grid grid-cols-3 gap-3 mt-6">
                      <div className="h-20 rounded-lg bg-white dark:bg-white/10 border border-primary-100 dark:border-white/5 p-2">
                        <div className="h-2 bg-green-500/60 rounded-full w-2/3 mb-2"></div>
                        <div className="h-2 bg-primary-100 dark:bg-white/20 rounded-full w-full"></div>
                      </div>
                      <div className="h-20 rounded-lg bg-white dark:bg-white/10 border border-primary-100 dark:border-white/5 p-2">
                        <div className="h-2 bg-blue-500/60 rounded-full w-2/3 mb-2"></div>
                        <div className="h-2 bg-primary-100 dark:bg-white/20 rounded-full w-full"></div>
                      </div>
                      <div className="h-20 rounded-lg bg-white dark:bg-white/10 border border-primary-100 dark:border-white/5 p-2">
                        <div className="h-2 bg-yellow-500/60 rounded-full w-2/3 mb-2"></div>
                        <div className="h-2 bg-primary-100 dark:bg-white/20 rounded-full w-full"></div>
                      </div>
                    </div>
                    <div className="h-10 rounded-lg bg-green-500/10 dark:bg-green-500/20 border border-green-400/30 dark:border-green-400/20 flex items-center justify-center">
                      <span className="text-xs text-green-700 dark:text-green-300">Цены собраны: 10 товаров</span>
                    </div>
                  </div>
                </div>
                <div className="absolute -top-4 -right-4 w-24 h-24 bg-primary-300/20 dark:bg-primary-400/20 rounded-full blur-xl"></div>
                <div className="absolute -bottom-4 -left-4 w-32 h-32 bg-blue-300/20 dark:bg-blue-400/20 rounded-full blur-xl"></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 bg-white dark:bg-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
              Всё, что нужно для анализа цен
            </h2>
            <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto text-lg">
              PriceMonitor закрывает полный цикл — от поиска конкурентов до отчёта с ценовыми различиями
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: Search,
                title: 'Добавление конкурентов',
                desc: 'Ручной ввод доменов сайтов для анализа. Гибкая настройка парсинга под каждый ресурс обеспечивает точный сбор данных.',
                color: 'text-blue-600 dark:text-blue-400',
                bg: 'bg-blue-50 dark:bg-blue-900/20'
              },
              {
                icon: Globe,
                title: 'Выбор региона',
                desc: 'Мониторинг в ключевых регионах России — от Москвы до Владивостока. Анализ конкурентов с учётом локальной выдачи.',
                color: 'text-emerald-600 dark:text-emerald-400',
                bg: 'bg-emerald-50 dark:bg-emerald-900/20'
              },
              {
                icon: MousePointerClick,
                title: 'CSS-селекторы',
                desc: 'Гибкая настройка правил извлечения данных под структуру сайта. Укажите, где искать название, цену — система адаптируется.',
                color: 'text-purple-600 dark:text-purple-400',
                bg: 'bg-purple-50 dark:bg-purple-900/20'
              },
              {
                icon: Database,
                title: 'Сбор цен',
                desc: 'Сбор актуальных товаров с ваших ресурсов и сайтов конкурентов. Извлечение ключевых характеристик.',
                color: 'text-orange-600 dark:text-orange-400',
                bg: 'bg-orange-50 dark:bg-orange-900/20'
              },
              {
                icon: BarChart3,
                title: 'Сравнительный отчёт',
                desc: 'Наглядное сравнение цен: кто дешевле, кто дороже и на сколько. Все товары автоматически группируются и связываются в единую таблицу.',
                color: 'text-rose-600 dark:text-rose-400',
                bg: 'bg-rose-50 dark:bg-rose-900/20'
              },
              {
                icon: Download,
                title: 'Экспорт данных',
                desc: 'Выгрузка отчётов в Excel и CSV. Удобный формат для анализа, печати или передачи данных коллегам.',
                color: 'text-cyan-600 dark:text-cyan-400',
                bg: 'bg-cyan-50 dark:bg-cyan-900/20'
              }
            ].map((feat, i) => (
              <div key={i} className="group card hover:shadow-lg hover:border-primary-200 dark:hover:border-primary-800 transition-all duration-300">
                <div className={`w-12 h-12 ${feat.bg} rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                  <feat.icon className={`h-6 w-6 ${feat.color}`} />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{feat.title}</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 bg-gray-50 dark:bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
              Как это работает
            </h2>
            <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto text-lg">
              От поиска до отчёта — три простых шага
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 relative">
            {[
              {
                step: '01',
                title: 'Создайте анализ',
                desc: 'Выберите конкурентов и укажите CSS-селекторы для названий и цен на их сайтах.',
                color: 'from-emerald-500 to-emerald-600'
              },
              {
                step: '02',
                title: 'Соберите цены',
                desc: 'Система автоматически спарсит товары и цены с вашего сайта и сайтов конкурентов.',
                color: 'from-purple-500 to-purple-600'
              },
              {
                step: '03',
                title: 'Анализируйте',
                desc: 'Изучите сравнительный отчёт, экспортируйте данные в Excel или CSV.',
                color: 'from-orange-500 to-orange-600'
              }
            ].map((item, i) => (
              <div key={i} className="relative">
                {i < 2 && (
                  <div className="hidden md:flex items-center absolute top-8 -translate-y-1/2 left-1/2 w-[calc(100%+2rem)] px-10 pointer-events-none">
                    <div className="flex-1 h-0.5 bg-gradient-to-r from-primary-300 to-primary-400 dark:from-primary-700 dark:to-primary-600"></div>
                    <div className="w-0 h-0 -ml-px shrink-0 border-y-[5px] border-y-transparent border-l-[9px] border-l-primary-400 dark:border-l-primary-600"></div>
                  </div>
                )}
                <div className="text-center">
                  <div className={`w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br ${item.color} shadow-lg flex items-center justify-center text-white font-bold text-lg`}>
                    {item.step}
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">{item.title}</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Target audience */}
      <section className="py-20 bg-white dark:bg-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
              Кому подойдёт PriceMonitor
            </h2>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: Store,
                title: 'Владельцы магазинов',
                desc: 'Забудьте о ручном мониторинге. Найдите конкурентов автоматически или добавьте сами — система сама сравнит цены.',
                color: 'text-blue-600 dark:text-blue-400',
                bg: 'bg-blue-50 dark:bg-blue-900/20'
              },
              {
                icon: ShoppingBag,
                title: 'Розничные сети',
                desc: 'Единая картина цен по всей сети. Настраивайте сбор под любой сайт и оперативно реагируйте.',
                color: 'text-purple-600 dark:text-purple-400',
                bg: 'bg-purple-50 dark:bg-purple-900/20'
              },
              {
                icon: Users,
                title: 'Маркетологи',
                desc: 'Объективные данные для акций и скидок. Исключите человеческие ошибки при сборе и выгружайте аналитику в Excel.',
                color: 'text-orange-600 dark:text-orange-400',
                bg: 'bg-orange-50 dark:bg-orange-900/20'
              }
            ].map((item, i) => (
              <div key={i} className="card text-center hover:shadow-lg transition-shadow">
                <div className={`w-14 h-14 ${item.bg} rounded-xl flex items-center justify-center mx-auto mb-4`}>
                  <item.icon className={`h-7 w-7 ${item.color}`} />
                </div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">{item.title}</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="py-20 bg-gray-50 dark:bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
              Преимущества
            </h2>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              {
                icon: Clock,
                title: 'Экономия времени',
                desc: 'Массовый сбор цен вместо ручного обхода десятков сайтов.',
              },
              {
                icon: Shield,
                title: 'Точность',
                desc: 'Исключение человеческого фактора и ошибок при сборе',
              },
              {
                icon: TrendingUp,
                title: 'Гибкость',
                desc: 'Возможность настройки анализа по нужным для вас параметрам',
              }
            ].map((item, i) => (
              <div key={i} className="text-center">
                <div className="w-16 h-16 bg-primary-50 dark:bg-primary-900/30 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <item.icon className="h-8 w-8 text-primary-600 dark:text-primary-400" />
                </div>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-1">{item.title}</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      {!user && (
        <section className="relative overflow-hidden py-24 bg-gradient-to-br from-primary-500 to-primary-700 dark:from-primary-600 dark:via-primary-700 dark:to-primary-800 text-white">
          <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PHBhdGggZD0iTTM2IDM0djItSDI0di0yaDEyek0zNiAyNHYySDI0di0yaDEyeiIvPjwvZz48L2c+PC9zdmc+')] opacity-20 dark:opacity-30"></div>
          <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <h2 className="text-3xl sm:text-4xl font-bold mb-6">
              Готовы попробовать?
            </h2>
            <p className="text-white/80 dark:text-primary-100 text-lg text-center whitespace-nowrap mb-8 max-w-full overflow-hidden">
              Начните уже сейчас, чтобы сравнить и анализировать товары конкурентов с вашими.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <button
                onClick={handleDemoClick}
                className="inline-flex items-center justify-center bg-white text-primary-700 px-8 py-3.5 rounded-xl font-semibold hover:bg-primary-50 transition-all shadow-lg shadow-primary-900/20 group"
              >
                Попробовать демо
                <ArrowRight className="h-4 w-4 ml-2 group-hover:translate-x-1 transition-transform" />
              </button>
              <Link
                to="/register"
                className="inline-flex items-center justify-center border-2 border-white/40 text-white px-8 py-3.5 rounded-xl font-semibold hover:bg-white/10 transition-colors"
              >
                Зарегистрироваться
              </Link>
            </div>
          </div>
        </section>
      )}


    </div>
  )
}
