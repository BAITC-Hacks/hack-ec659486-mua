/** S02 example: manually curated from the organizer DOCX, with verified and candidate findings.
 * The published S01 contract is the source of truth for this fixture.
 */
import type { Report } from "@/lib/types";

export const demoReport: Report = {
  "run_id": "demo-case11",
  "created_at": "2026-09-23T09:20:00Z",
  "unit_changes": [
    {
      "unit_before": {
        "id": "dnm-before",
        "name": "Департамент непрерывного мониторинга системы внутреннего контроля",
        "version": "before",
        "parent": null,
        "sources": [
          {
            "doc_id": "case11-before",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
            "version": "before",
            "clause_number": "3.4",
            "quote": "а. Департамент непрерывного мониторинга системы внутреннего контроля (ДНМ).",
            "clause_id": "case11-before-3.4"
          }
        ]
      },
      "unit_after": {
        "id": "dnm-after",
        "name": "Департамент непрерывного мониторинга системы внутреннего контроля",
        "version": "after",
        "parent": null,
        "sources": [
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "3.4",
            "quote": "в. Департамент непрерывного мониторинга системы внутреннего контроля (ДНМ).",
            "clause_id": "case11-after-3.4"
          }
        ]
      },
      "status": "kept",
      "note": "ДНМ присутствует в п. 3.4 обеих редакций. Сохранение подразделения не означает неизменность всех его функций.",
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "3.4",
          "quote": "а. Департамент непрерывного мониторинга системы внутреннего контроля (ДНМ).",
          "clause_id": "case11-before-3.4"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "3.4",
          "quote": "в. Департамент непрерывного мониторинга системы внутреннего контроля (ДНМ).",
          "clause_id": "case11-after-3.4"
        }
      ],
      "id": "unit-change-1"
    },
    {
      "unit_before": {
        "id": "dkkm-before",
        "name": "Департамент контроля качества аудита и методологии",
        "version": "before",
        "parent": null,
        "sources": [
          {
            "doc_id": "case11-before",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
            "version": "before",
            "clause_number": "3.4",
            "quote": "б. Департамент контроля качества аудита и методологии (ДККМ).",
            "clause_id": "case11-before-3.4"
          }
        ]
      },
      "unit_after": {
        "id": "dkkm-after",
        "name": "Департамент контроля качества аудита и методологии",
        "version": "after",
        "parent": null,
        "sources": [
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "3.4",
            "quote": "г. Департамент контроля качества аудита и методологии (ДККМ).",
            "clause_id": "case11-after-3.4"
          }
        ]
      },
      "status": "transformed",
      "note": "Название ДККМ сохранено, перечень подчинённых должностей изменён: п. 3.8 редакции 8 → п. 3.9 редакции 9. Это изменение состава подразделения; юридическое переименование или слияние документами не подтверждено.",
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "3.8",
          "quote": "б. Менеджер по контролю качества аудита и методологии.",
          "clause_id": "case11-before-3.8"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "3.9",
          "quote": "б. Руководитель направления.",
          "clause_id": "case11-after-3.9"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "3.4",
          "quote": "б. Департамент контроля качества аудита и методологии (ДККМ).",
          "clause_id": "case11-before-3.4"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "3.4",
          "quote": "г. Департамент контроля качества аудита и методологии (ДККМ).",
          "clause_id": "case11-after-3.4"
        }
      ],
      "id": "unit-change-2"
    },
    {
      "unit_before": null,
      "unit_after": {
        "id": "ditaad-after",
        "name": "Департамент ИТ-аудита и анализа данных",
        "version": "after",
        "parent": null,
        "sources": [
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "3.4",
            "quote": "а. Департамент ИТ-аудита и анализа данных (ДИТААД).",
            "clause_id": "case11-after-3.4"
          }
        ]
      },
      "status": "created",
      "note": "ДИТААД добавлен в перечень подразделений БВА п. 3.4 редакции 9; в перечне редакции 8 отсутствует. Дата фактического создания не установлена.",
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "3.4",
          "quote": "а. Департамент непрерывного мониторинга системы внутреннего контроля (ДНМ).\nб. Департамент контроля качества аудита и методологии (ДККМ).",
          "clause_id": "case11-before-3.4"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "3.4",
          "quote": "а. Департамент ИТ-аудита и анализа данных (ДИТААД).",
          "clause_id": "case11-after-3.4"
        }
      ],
      "id": "unit-change-3"
    }
  ],
  "function_matches": [
    {
      "before": [
        {
          "id": "dnm-before-plan-proposals",
          "unit_id": "dnm-before",
          "text": "готовит предложения для включения в план работ БВА;",
          "category": "function",
          "signature": "plan-proposals",
          "sources": [
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.4.2",
              "quote": "5.4.2. готовит предложения для включения в план работ БВА;",
              "clause_id": "case11-before-5.4.2"
            },
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.4",
              "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
              "clause_id": "case11-before-5.4"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДНМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.4"
          ]
        }
      ],
      "after": [
        {
          "id": "dnm-after-plan-proposals",
          "unit_id": "dnm-after",
          "text": "готовит предложения для включения в план работ БВА;",
          "category": "function",
          "signature": "plan-proposals",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.4.2",
              "quote": "5.4.2. готовит предложения для включения в план работ БВА;",
              "clause_id": "case11-after-5.4.2"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.4",
              "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
              "clause_id": "case11-after-5.4"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДНМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.4"
          ]
        }
      ],
      "status": "kept",
      "confidence": 1.0,
      "note": "Обязанность ДНМ сохранена дословно; изменение номера пункта не является переносом функции.",
      "id": "function-match-1",
      "kind": "one_to_one",
      "verification": "exact",
      "verified": true,
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.4.2",
          "quote": "5.4.2. готовит предложения для включения в план работ БВА;",
          "clause_id": "case11-before-5.4.2"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.4",
          "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "clause_id": "case11-before-5.4"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.4.2",
          "quote": "5.4.2. готовит предложения для включения в план работ БВА;",
          "clause_id": "case11-after-5.4.2"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.4",
          "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "clause_id": "case11-after-5.4"
        }
      ]
    },
    {
      "before": [
        {
          "id": "dnm-before-continuous-analysis",
          "unit_id": "dnm-before",
          "text": "анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
          "category": "function",
          "signature": "continuous-analysis",
          "sources": [
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.4.6",
              "quote": "5.4.6. анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
              "clause_id": "case11-before-5.4.6"
            },
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.4",
              "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
              "clause_id": "case11-before-5.4"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДНМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.4"
          ]
        }
      ],
      "after": [
        {
          "id": "dnm-after-continuous-analysis",
          "unit_id": "dnm-after",
          "text": "анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
          "category": "function",
          "signature": "continuous-analysis",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.4.5",
              "quote": "5.4.5. анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
              "clause_id": "case11-after-5.4.5"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.4",
              "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
              "clause_id": "case11-after-5.4"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДНМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.4"
          ]
        }
      ],
      "status": "kept",
      "confidence": 1.0,
      "note": "Обязанность ДНМ сохранена дословно; изменение номера пункта не является переносом функции.",
      "id": "function-match-2",
      "kind": "one_to_one",
      "verification": "exact",
      "verified": true,
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.4.6",
          "quote": "5.4.6. анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
          "clause_id": "case11-before-5.4.6"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.4",
          "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "clause_id": "case11-before-5.4"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.4.5",
          "quote": "5.4.5. анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
          "clause_id": "case11-after-5.4.5"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.4",
          "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "clause_id": "case11-after-5.4"
        }
      ]
    },
    {
      "before": [
        {
          "id": "dkkm-before-work-reports",
          "unit_id": "dkkm-before",
          "text": "готовит отчеты об итогах выполнения плана работы БВА на ежеквартальной основе и по итогам года в соответствии с требованиями настоящего Положения;",
          "category": "function",
          "signature": "work-reports",
          "sources": [
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.5.5",
              "quote": "5.5.5. готовит отчеты об итогах выполнения плана работы БВА на ежеквартальной основе и по итогам года в соответствии с требованиями настоящего Положения;",
              "clause_id": "case11-before-5.5.5"
            },
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.5",
              "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
              "clause_id": "case11-before-5.5"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДККМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.5"
          ]
        }
      ],
      "after": [
        {
          "id": "dkkm-after-work-reports",
          "unit_id": "dkkm-after",
          "text": "готовит отчеты об итогах выполнения плана работы БВА в соответствии с требованиями настоящего Положения;",
          "category": "function",
          "signature": "work-reports",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.5.3",
              "quote": "5.5.3. готовит отчеты об итогах выполнения плана работы БВА в соответствии с требованиями настоящего Положения;",
              "clause_id": "case11-after-5.5.3"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.5",
              "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
              "clause_id": "case11-after-5.5"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДККМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.5"
          ]
        }
      ],
      "status": "changed",
      "confidence": 0.95,
      "note": "В обязанности ДККМ удалено явное указание на ежеквартальную и годовую периодичность. Отчётность сохраняется; это не доказывает отмену сроков в других пунктах.",
      "id": "function-match-3",
      "kind": "one_to_one",
      "verification": "lexical",
      "verified": true,
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.5.5",
          "quote": "5.5.5. готовит отчеты об итогах выполнения плана работы БВА на ежеквартальной основе и по итогам года в соответствии с требованиями настоящего Положения;",
          "clause_id": "case11-before-5.5.5"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.5",
          "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
          "clause_id": "case11-before-5.5"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.5.3",
          "quote": "5.5.3. готовит отчеты об итогах выполнения плана работы БВА в соответствии с требованиями настоящего Положения;",
          "clause_id": "case11-after-5.5.3"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.5",
          "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
          "clause_id": "case11-after-5.5"
        }
      ]
    },
    {
      "before": [
        {
          "id": "dkkm-before-dzo-interaction",
          "unit_id": "dkkm-before",
          "text": "взаимодействует c Руководителями Общества, подразделениями Общества, ДЗО по всему кругу вопросов, касающихся выполнения функций непрерывного аудита;",
          "category": "function",
          "signature": "dzo-interaction",
          "sources": [
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.5.13",
              "quote": "5.5.13. взаимодействует c Руководителями Общества, подразделениями Общества, ДЗО по всему кругу вопросов, касающихся выполнения функций непрерывного аудита;",
              "clause_id": "case11-before-5.5.13"
            },
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.5",
              "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
              "clause_id": "case11-before-5.5"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДККМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.5"
          ]
        }
      ],
      "after": [
        {
          "id": "dkkm-after-dzo-interaction",
          "unit_id": "dkkm-after",
          "text": "взаимодействует c Руководителями Общества, подразделениями Общества, ДЗО по всему кругу вопросов, касающихся выполнения функций внутреннего аудита;",
          "category": "function",
          "signature": "dzo-interaction",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.5.9",
              "quote": "5.5.9. взаимодействует c Руководителями Общества, подразделениями Общества, ДЗО по всему кругу вопросов, касающихся выполнения функций внутреннего аудита;",
              "clause_id": "case11-after-5.5.9"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.5",
              "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
              "clause_id": "case11-after-5.5"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДККМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.5"
          ]
        }
      ],
      "status": "changed",
      "confidence": 0.95,
      "note": "Взаимодействие ДККМ с подразделениями и ДЗО расширено в формулировке с непрерывного аудита до внутреннего аудита.",
      "id": "function-match-4",
      "kind": "one_to_one",
      "verification": "lexical",
      "verified": true,
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.5.13",
          "quote": "5.5.13. взаимодействует c Руководителями Общества, подразделениями Общества, ДЗО по всему кругу вопросов, касающихся выполнения функций непрерывного аудита;",
          "clause_id": "case11-before-5.5.13"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.5",
          "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
          "clause_id": "case11-before-5.5"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.5.9",
          "quote": "5.5.9. взаимодействует c Руководителями Общества, подразделениями Общества, ДЗО по всему кругу вопросов, касающихся выполнения функций внутреннего аудита;",
          "clause_id": "case11-after-5.5.9"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.5",
          "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
          "clause_id": "case11-after-5.5"
        }
      ]
    },
    {
      "before": [
        {
          "id": "audit-direction-before-control-remediation",
          "unit_id": null,
          "text": "организует контроль устранения недостатков и нарушений, выявленных в ходе проведения проверок БВА;",
          "category": "function",
          "signature": "control-remediation",
          "sources": [
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_id": "case11-before-5.3.6",
              "clause_number": "5.3.6",
              "quote": "5.3.6. организует контроль устранения недостатков и нарушений, выявленных в ходе проведения проверок БВА;"
            },
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_id": "case11-before-5.3",
              "clause_number": "5.3",
              "quote": "5.3. Директор направления внутреннего аудита:"
            }
          ],
          "modality": "duty",
          "executor": "Директор направления внутреннего аудита",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.3"
          ]
        }
      ],
      "after": [],
      "status": "lost",
      "confidence": 0.45,
      "note": "Кандидат в потери — требует проверки по всему документу редакции 9. Пункт 5.3.6 редакции 8 закреплял контроль устранения нарушений за директором направления внутреннего аудита; п. 5.3.7 редакции 9 возлагает аналогичное действие на директоров ДИТААД и ДОА. Вероятен перенос, а не утрата функции БВА.",
      "id": "function-match-5",
      "kind": "one_to_one",
      "verification": "lexical",
      "verified": false,
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_id": "case11-before-5.3.6",
          "clause_number": "5.3.6",
          "quote": "5.3.6. организует контроль устранения недостатков и нарушений, выявленных в ходе проведения проверок БВА;"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_id": "case11-before-5.3",
          "clause_number": "5.3",
          "quote": "5.3. Директор направления внутреннего аудита:"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_id": "case11-after-5.3.7",
          "clause_number": "5.3.7",
          "quote": "5.3.7. организуют контроль устранения недостатков и нарушений, выявленных в ходе проведения проверок БВА, обеспечивают и совершенствуют работу системы мониторинга действий (корректирующих мер) Руководителей Общества, предпринимаемых по результатам внутренних аудитов и проектов."
        }
      ]
    },
    {
      "before": [
        {
          "id": "dkkm-before-own-plan-proposals",
          "unit_id": "dkkm-before",
          "text": "готовит предложения для включения в план работ БВА;",
          "category": "function",
          "signature": "own-plan-proposals",
          "sources": [
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.5.10",
              "quote": "5.5.10. готовит предложения для включения в план работ БВА;",
              "clause_id": "case11-before-5.5.10"
            },
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.5",
              "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
              "clause_id": "case11-before-5.5"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДККМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.5"
          ]
        }
      ],
      "after": [],
      "status": "lost",
      "confidence": 0.55,
      "note": "Кандидат в потери — требует проверки по всему документу редакции 9. Потенциальная потеря отдельной обязанности ДККМ готовить предложения в план. Консолидация предложений и формирование плана сохранены в п. 5.5.7; требуется проверить распределение ответственности.",
      "id": "function-match-6",
      "kind": "one_to_one",
      "verification": "lexical",
      "verified": false,
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.5.10",
          "quote": "5.5.10. готовит предложения для включения в план работ БВА;",
          "clause_id": "case11-before-5.5.10"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.5",
          "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
          "clause_id": "case11-before-5.5"
        }
      ]
    },
    {
      "before": [],
      "after": [
        {
          "id": "ditaad-after-strategic-management",
          "unit_id": "ditaad-after",
          "text": "обеспечивают стратегическое управление аудитом по направлениям в зоне ответственности в соответствии с п. 3 настоящего Положения и планом работ БВА;",
          "category": "function",
          "signature": "strategic-management",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3.1",
              "quote": "5.3.1. обеспечивают стратегическое управление аудитом по направлениям в зоне ответственности в соответствии с п. 3 настоящего Положения и планом работ БВА;",
              "clause_id": "case11-after-5.3.1"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3",
              "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
              "clause_id": "case11-after-5.3"
            }
          ],
          "modality": "duty",
          "executor": "Директоры ДИТААД и ДОА",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.3"
          ]
        }
      ],
      "status": "new",
      "confidence": 0.85,
      "note": "Новое явное закрепление по сравнению с сопоставленными пунктами; не доказательство отсутствия функции во всём БВА. Новое явное закрепление стратегического управления за директорами ДИТААД/ДОА. Статус относится к формулировке и новому подразделению, а не к отсутствию управления аудитом до реорганизации.",
      "id": "function-match-7",
      "kind": "one_to_one",
      "verification": "lexical",
      "verified": true,
      "sources": [
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.3.1",
          "quote": "5.3.1. обеспечивают стратегическое управление аудитом по направлениям в зоне ответственности в соответствии с п. 3 настоящего Положения и планом работ БВА;",
          "clause_id": "case11-after-5.3.1"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.3",
          "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "clause_id": "case11-after-5.3"
        }
      ]
    },
    {
      "before": [],
      "after": [
        {
          "id": "bva-after-disclose-dzo-conflict",
          "unit_id": null,
          "text": "Информировать о потенциальном конфликте при совмещении в отчетах и плане БВА.",
          "category": "function",
          "signature": "disclose-dzo-conflict",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_id": "case11-after-4.4",
              "clause_number": "4.4",
              "quote": "а. информирует о потенциальном конфликте при совмещении в отчетах и плане БВА;"
            }
          ],
          "modality": "duty",
          "executor": "БВА",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "4.4"
          ]
        }
      ],
      "status": "new",
      "confidence": 0.85,
      "note": "В редакции 9 добавлено явное информирование о потенциальном конфликте при совмещении ролей в ДЗО (п. 4.4). В редакции 8 соответствующий текст п. 4.4 такого условия не содержал.",
      "id": "function-match-8",
      "kind": "one_to_one",
      "verification": "lexical",
      "verified": true,
      "sources": [
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_id": "case11-after-4.4",
          "clause_number": "4.4",
          "quote": "а. информирует о потенциальном конфликте при совмещении в отчетах и плане БВА;"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_id": "case11-before-4.4",
          "clause_number": "4.4",
          "quote": "4.4. Организация выполнения целей и задач внутреннего аудита ДЗО на основании заключенного договора, осуществление общего руководства и распределение обязанностей между работниками БВА по целям и задачам внутреннего аудита ДЗО на основании заключенного договора."
        }
      ]
    },
    {
      "before": [
        {
          "id": "dnm-before-assurance-results",
          "unit_id": "dnm-before",
          "text": "Использовать результаты других субъектов СВК и оценивать качество и надёжность этих результатов.",
          "category": "function",
          "signature": "assurance-results",
          "sources": [
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.4.4",
              "quote": "а. использования в своей деятельности результатов работы других субъектов СВК и иных заинтересованных сторон, включая оценку качества и надежности результатов работ субъектов СВК (в т.ч. применяемую методологию, процедуры и техники, используемые при оценке, объем и характер работ);",
              "clause_id": "case11-before-5.4.4"
            },
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.4",
              "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
              "clause_id": "case11-before-5.4"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДНМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.4"
          ]
        }
      ],
      "after": [
        {
          "id": "ditaad-after-assurance-results",
          "unit_id": "ditaad-after",
          "text": "Использовать результаты других субъектов СВК и оценивать качество и надёжность этих результатов.",
          "category": "function",
          "signature": "assurance-results",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3.3",
              "quote": "а. использования в своей деятельности результатов работы других субъектов СВК и иных заинтересованных сторон, включая оценку качества и надежности результатов работ субъектов СВК (в т.ч. применяемую методологию, процедуры и техники, используемые при оценке, объем и характер работ);",
              "clause_id": "case11-after-5.3.3"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3",
              "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
              "clause_id": "case11-after-5.3"
            }
          ],
          "modality": "duty",
          "executor": "Директоры ДИТААД и ДОА",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.3",
            "5.3.3"
          ]
        }
      ],
      "status": "moved",
      "confidence": 1.0,
      "note": "Обязанность из перечня директора ДНМ (п. 5.4.4 редакции 8) перенесена в общий перечень директоров ДИТААД и ДОА (п. 5.3.3 редакции 9). В этой строке показан ДИТААД; перенос не является исключительным закреплением только за ним.",
      "id": "function-match-9",
      "kind": "one_to_one",
      "verification": "lexical",
      "verified": true,
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.4.4",
          "quote": "а. использования в своей деятельности результатов работы других субъектов СВК и иных заинтересованных сторон, включая оценку качества и надежности результатов работ субъектов СВК (в т.ч. применяемую методологию, процедуры и техники, используемые при оценке, объем и характер работ);",
          "clause_id": "case11-before-5.4.4"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.4",
          "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "clause_id": "case11-before-5.4"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.3.3",
          "quote": "а. использования в своей деятельности результатов работы других субъектов СВК и иных заинтересованных сторон, включая оценку качества и надежности результатов работ субъектов СВК (в т.ч. применяемую методологию, процедуры и техники, используемые при оценке, объем и характер работ);",
          "clause_id": "case11-after-5.3.3"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.3",
          "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "clause_id": "case11-after-5.3"
        }
      ]
    },
    {
      "before": [
        {
          "id": "dnm-before-assurance-map",
          "unit_id": "dnm-before",
          "text": "Выявлять риски с недостаточным или дублирующим покрытием в рамках Карты гарантий.",
          "category": "function",
          "signature": "assurance-map",
          "sources": [
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.4.4",
              "quote": "б. выявления рисков с недостаточным или дублирующим покрытием субъектами СВК и иными заинтересованными сторонами в рамках Карты гарантий;",
              "clause_id": "case11-before-5.4.4"
            },
            {
              "doc_id": "case11-before",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
              "version": "before",
              "clause_number": "5.4",
              "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
              "clause_id": "case11-before-5.4"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДНМ",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.4"
          ]
        }
      ],
      "after": [
        {
          "id": "ditaad-after-assurance-map",
          "unit_id": "ditaad-after",
          "text": "Выявлять риски с недостаточным или дублирующим покрытием в рамках Карты гарантий.",
          "category": "function",
          "signature": "assurance-map",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3.3",
              "quote": "б. выявления рисков с недостаточным или дублирующим покрытием субъектами СВК и иными заинтересованными сторонами в рамках Карты гарантий;",
              "clause_id": "case11-after-5.3.3"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3",
              "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
              "clause_id": "case11-after-5.3"
            }
          ],
          "modality": "duty",
          "executor": "Директоры ДИТААД и ДОА",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.3",
            "5.3.3"
          ]
        },
        {
          "id": "doa-after-assurance-map",
          "unit_id": null,
          "text": "Выявлять риски с недостаточным или дублирующим покрытием в рамках Карты гарантий.",
          "category": "function",
          "signature": "assurance-map",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3.3",
              "quote": "б. выявления рисков с недостаточным или дублирующим покрытием субъектами СВК и иными заинтересованными сторонами в рамках Карты гарантий;",
              "clause_id": "case11-after-5.3.3"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3",
              "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
              "clause_id": "case11-after-5.3"
            }
          ],
          "modality": "duty",
          "executor": "Директор ДОА",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.3",
            "5.3.3"
          ]
        }
      ],
      "status": "moved",
      "confidence": 1.0,
      "note": "Формулировка ред. 8, п. 5.4.4, у ДНМ сопоставлена с общим пунктом ред. 9, п. 5.3.3: обе роли ДИТААД и ДОА. Показана связь один-ко-многим, без утверждения об исключительном закреплении.",
      "id": "function-match-10",
      "kind": "split",
      "verification": "lexical",
      "verified": true,
      "sources": [
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.4.4",
          "quote": "б. выявления рисков с недостаточным или дублирующим покрытием субъектами СВК и иными заинтересованными сторонами в рамках Карты гарантий;",
          "clause_id": "case11-before-5.4.4"
        },
        {
          "doc_id": "case11-before",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
          "version": "before",
          "clause_number": "5.4",
          "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "clause_id": "case11-before-5.4"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.3.3",
          "quote": "б. выявления рисков с недостаточным или дублирующим покрытием субъектами СВК и иными заинтересованными сторонами в рамках Карты гарантий;",
          "clause_id": "case11-after-5.3.3"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.3",
          "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "clause_id": "case11-after-5.3"
        }
      ]
    }
  ],
  "duplicates": [
    {
      "function_a": {
        "id": "ditaad-after-continuous-analysis",
        "unit_id": "ditaad-after",
        "text": "Анализировать результаты непрерывного аудита и готовить материалы Главному аудитору.",
        "category": "function",
        "signature": "continuous-analysis",
        "sources": [
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "5.3.8",
            "quote": "5.3.8. анализируют результаты проверок БВА и непрерывного аудита, готовят материалы и предложения в зоне ответственности для представления Главному аудитору;",
            "clause_id": "case11-after-5.3.8"
          },
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "5.3",
            "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
            "clause_id": "case11-after-5.3"
          }
        ],
        "modality": "duty",
        "executor": "Директоры ДИТААД и ДОА",
        "action": null,
        "object": null,
        "context_clause_numbers": [
          "5.3"
        ]
      },
      "function_b": {
        "id": "dnm-after-continuous-analysis",
        "unit_id": "dnm-after",
        "text": "анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
        "category": "function",
        "signature": "continuous-analysis",
        "sources": [
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "5.4.5",
            "quote": "5.4.5. анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
            "clause_id": "case11-after-5.4.5"
          },
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "5.4",
            "quote": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
            "clause_id": "case11-after-5.4"
          }
        ],
        "modality": "duty",
        "executor": "Директор ДНМ",
        "action": null,
        "object": null,
        "context_clause_numbers": [
          "5.4"
        ]
      },
      "similarity": 0.92,
      "note": "Кандидат: Потенциальное пересечение анализа результатов непрерывного аудита у ДИТААД/ДОА и ДНМ. В обоих пунктах есть ограничение зоной ответственности; фактический дубль требует проверки границ этих зон.",
      "id": "duplicate-1",
      "verified": false,
      "verification_note": "Требует проверки одинакового действия и объекта у двух исполнителей: цитаты показывают пересечение темы, но не доказывают точный дубль."
    },
    {
      "function_a": {
        "id": "ditaad-after-methodology",
        "unit_id": "ditaad-after",
        "text": "участвуют в разработке ВНД БВА;",
        "category": "function",
        "signature": "methodology",
        "sources": [
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "5.3.12",
            "quote": "5.3.12. участвуют в разработке ВНД БВА;",
            "clause_id": "case11-after-5.3.12"
          },
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "5.3",
            "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
            "clause_id": "case11-after-5.3"
          }
        ],
        "modality": "duty",
        "executor": "Директоры ДИТААД и ДОА",
        "action": null,
        "object": null,
        "context_clause_numbers": [
          "5.3"
        ]
      },
      "function_b": {
        "id": "dkkm-after-methodology",
        "unit_id": "dkkm-after",
        "text": "разрабатывает методические материалы, актуализирует ВНД, регламентирующие деятельность внутреннего аудита (единая методология внутреннего аудита);",
        "category": "function",
        "signature": "methodology",
        "sources": [
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "5.5.4",
            "quote": "5.5.4. разрабатывает методические материалы, актуализирует ВНД, регламентирующие деятельность внутреннего аудита (единая методология внутреннего аудита);",
            "clause_id": "case11-after-5.5.4"
          },
          {
            "doc_id": "case11-after",
            "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
            "version": "after",
            "clause_number": "5.5",
            "quote": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
            "clause_id": "case11-after-5.5"
          }
        ],
        "modality": "duty",
        "executor": "Директор ДККМ",
        "action": null,
        "object": null,
        "context_clause_numbers": [
          "5.5"
        ]
      },
      "similarity": 0.82,
      "note": "Кандидат: ДИТААД/ДОА участвуют в разработке ВНД БВА, ДККМ разрабатывает методические материалы и актуализирует ВНД. Возможное пересечение работ; участие и методологическое владение могут быть намеренно разделены.",
      "id": "duplicate-2",
      "verified": false,
      "verification_note": "Требует проверки одинакового действия и объекта у двух исполнителей: цитаты показывают пересечение темы, но не доказывают точный дубль."
    }
  ],
  "conflicts": [
    {
      "rule_id": "executes_and_controls",
      "title": "Выполняет и контролирует: риск самопроверки аудиторской команды",
      "units": [
        "ditaad-after"
      ],
      "functions": [
        {
          "id": "ditaad-after-conduct-audits",
          "unit_id": "ditaad-after",
          "text": "Проводить проверки и обеспечивать выполнение плана работ БВА.",
          "category": "function",
          "signature": "conduct-audits",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3.5",
              "quote": "5.3.5. проводят проверки и обеспечивают выполнение плана работ БВА в том числе:",
              "clause_id": "case11-after-5.3.5"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3",
              "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
              "clause_id": "case11-after-5.3"
            }
          ],
          "modality": "duty",
          "executor": "Директоры ДИТААД и ДОА",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.3"
          ]
        },
        {
          "id": "ditaad-after-control-audit-team",
          "unit_id": "ditaad-after",
          "text": "Контролировать качество работы проектной команды.",
          "category": "function",
          "signature": "control-audit-team",
          "sources": [
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3.5",
              "quote": "б. контроль качества работы проектной команды;",
              "clause_id": "case11-after-5.3.5"
            },
            {
              "doc_id": "case11-after",
              "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
              "version": "after",
              "clause_number": "5.3",
              "quote": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
              "clause_id": "case11-after-5.3"
            }
          ],
          "modality": "duty",
          "executor": "Директоры ДИТААД и ДОА",
          "action": null,
          "object": null,
          "context_clause_numbers": [
            "5.3"
          ]
        }
      ],
      "explanation": "Кандидат на проверку разделения исполнения и контроля, не подтверждённый конфликт интересов. По п. 5.3.5 роль проводит аудиторскую проверку и контролирует качество проектной команды; п. 5.5.2 отдельно закрепляет оценку качества за ДККМ. Фактический контролёр того же объекта требует выяснения.",
      "sources": [
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.3.5",
          "quote": "5.3.5. проводят проверки и обеспечивают выполнение плана работ БВА в том числе:",
          "clause_id": "case11-after-5.3.5"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.3.5",
          "quote": "б. контроль качества работы проектной команды;",
          "clause_id": "case11-after-5.3.5"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_number": "5.5.2",
          "quote": "5.5.2. организует непрерывный мониторинг качества деятельности внутреннего аудита; организует периодические внутренние и внешние оценки качества всего спектра деятельности внутреннего аудита (Программа обеспечения и повышения качества внутреннего аудита);",
          "clause_id": "case11-after-5.5.2"
        }
      ],
      "id": "conflict-1",
      "role_pattern": "выполняет + контролирует",
      "severity": "low",
      "verified": false,
      "verification_note": "Требует проверки объекта и независимости контролёра. Контроль качества работы собственной команды по п. 5.3.5 не доказывает конфликт; п. 5.5.2 предусматривает отдельную оценку качества ДККМ."
    }
  ],
  "conclusion_md": "# Сравнение редакций 8 и 9 Положения о внутреннем аудите\n1. БВА возглавляет Главный аудитор (обе редакции, п. 1.4); здесь приведена выборка для интерфейса.\n2. ДНМ сохранён в структуре БВА (обе редакции, п. 3.4).\n3. Состав должностей ДККМ изменён при сохранении названия (ред. 8, п. 3.8; ред. 9, п. 3.9).\n4. ДИТААД добавлен в перечень; редакция 9 также включает ДОА (обе редакции, п. 3.4).\n5. Предложения в план и анализ непрерывного аудита ДНМ сохранены (ред. 8, пп. 5.4.2, 5.4.6; ред. 9, пп. 5.4.2, 5.4.5).\n6. Формулировки отчётности и взаимодействия ДККМ с ДЗО изменены (ред. 8, пп. 5.5.5, 5.5.13; ред. 9, пп. 5.5.3, 5.5.9).\n7. Пункт о Карте гарантий ДНМ сопоставлен с общей обязанностью ДИТААД и ДОА (ред. 8, п. 5.4.4; ред. 9, п. 5.3.3).\n8. В ред. 9 добавлено информирование о потенциальном конфликте при совмещении ролей в ДЗО (п. 4.4); запрет на операционные обязанности сохранён отдельно (п. 5.8.1).\n9. Контроль устранения нарушений у прежнего директора направления и два возможных дубля и конфликт требуют проверки; они не признаны доказанной потерей, дублем или конфликтом (ред. 8, п. 5.3.6; ред. 9, пп. 5.3.5, 5.3.7, 5.5.2).",
  "stats": {
    "units_before": 2,
    "units_after": 3,
    "functions_before": 8,
    "functions_after": 14,
    "matches": 8,
    "lost": 0,
    "new": 2,
    "duplicates": 0,
    "conflicts": 0,
    "unverified_candidates": 5
  },
  "before_documents": [
    {
      "id": "case11-before",
      "name": "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx",
      "version": "before",
      "kind": "polozhenie",
      "clauses": [
        {
          "id": "case11-before-1.4",
          "number": "1.4",
          "section": "1. Общие положения",
          "text": "1.4. Руководство БВА осуществляет Главный аудитор в соответствии с Уставом Общества.",
          "index": 12,
          "section_path": [
            "1.",
            "1. Общие положения"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-before-3.4",
          "number": "3.4",
          "section": "3. Структура и организация работы внутреннего аудита",
          "text": "3.4. БВА состоит из следующих структурных подразделений:\nа. Департамент непрерывного мониторинга системы внутреннего контроля (ДНМ).\nб. Департамент контроля качества аудита и методологии (ДККМ).",
          "index": 103,
          "section_path": [
            "3.",
            "3. Структура и организация работы внутреннего аудита"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-before-3.8",
          "number": "3.8",
          "section": "3. Структура и организация работы внутреннего аудита",
          "text": "3.8. Директору ДККМ подчиняются работники ДККМ в соответствии со штатным расписанием в составе следующих должностей:\nа. Директор по контролю качества аудита и методологии.\nб. Менеджер по контролю качества аудита и методологии.\nв. Директор проектов ДККМ.\nг. Менеджер по аудиту.",
          "index": 116,
          "section_path": [
            "3.",
            "3. Структура и организация работы внутреннего аудита"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-before-4.4",
          "number": "4.4",
          "section": "4. Внутренний аудит в ДЗО При взаимодействии с дочерними и зависимыми обществами в части организации внутреннего аудита, включая заключение договора возмездного оказания услуг на выполнение функции внутреннего аудита в ДЗО, Главный аудитор или уполномоченное им лицо осуществляет функциональное руководство и координацию деятельности подразделения ДЗО, осуществляющего функции внутреннего аудита, в соответствии с нормативными документами Общества, в том числе по следующим вопросам:",
          "text": "4.4. Организация выполнения целей и задач внутреннего аудита ДЗО на основании заключенного договора, осуществление общего руководства и распределение обязанностей между работниками БВА по целям и задачам внутреннего аудита ДЗО на основании заключенного договора.",
          "index": 126,
          "section_path": [
            "4.",
            "4. Внутренний аудит в ДЗО При взаимодействии с дочерними и зависимыми обществами в части организации внутреннего аудита, включая заключение договора возмездного оказания услуг на выполнение функции внутреннего аудита в ДЗО, Главный аудитор или уполномоченное им лицо осуществляет функциональное руководство и координацию деятельности подразделения ДЗО, осуществляющего функции внутреннего аудита, в соответствии с нормативными документами Общества, в том числе по следующим вопросам:"
          ],
          "lead_in": null,
          "modality": "duty"
        },
        {
          "id": "case11-before-5.3",
          "number": "5.3",
          "section": "5. Права и обязанности",
          "text": "5.3. Директор направления внутреннего аудита:",
          "index": 149,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-before-5.3.6",
          "number": "5.3.6",
          "section": "5. Права и обязанности",
          "text": "5.3.6. организует контроль устранения недостатков и нарушений, выявленных в ходе проведения проверок БВА;",
          "index": 163,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-before-5.4",
          "number": "5.4",
          "section": "5. Права и обязанности",
          "text": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "index": 170,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-before-5.4.2",
          "number": "5.4.2",
          "section": "5. Права и обязанности",
          "text": "5.4.2. готовит предложения для включения в план работ БВА;",
          "index": 172,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "modality": "duty"
        },
        {
          "id": "case11-before-5.4.4",
          "number": "5.4.4",
          "section": "5. Права и обязанности",
          "text": "5.4.4. взаимодействует с субъектами СВК Общества в части:\nа. использования в своей деятельности результатов работы других субъектов СВК и иных заинтересованных сторон, включая оценку качества и надежности результатов работ субъектов СВК (в т.ч. применяемую методологию, процедуры и техники, используемые при оценке, объем и характер работ);\nб. выявления рисков с недостаточным или дублирующим покрытием субъектами СВК и иными заинтересованными сторонами в рамках Карты гарантий;",
          "index": 174,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "modality": "duty"
        },
        {
          "id": "case11-before-5.4.6",
          "number": "5.4.6",
          "section": "5. Права и обязанности",
          "text": "5.4.6. анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
          "index": 178,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "modality": "duty"
        },
        {
          "id": "case11-before-5.5",
          "number": "5.5",
          "section": "5. Права и обязанности",
          "text": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
          "index": 184,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-before-5.5.5",
          "number": "5.5.5",
          "section": "5. Права и обязанности",
          "text": "5.5.5. готовит отчеты об итогах выполнения плана работы БВА на ежеквартальной основе и по итогам года в соответствии с требованиями настоящего Положения;",
          "index": 189,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        },
        {
          "id": "case11-before-5.5.8",
          "number": "5.5.8",
          "section": "5. Права и обязанности",
          "text": "5.5.8. выносит предложения по повышению профессионального уровня работников БВА Главному аудитору;",
          "index": 192,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        },
        {
          "id": "case11-before-5.5.10",
          "number": "5.5.10",
          "section": "5. Права и обязанности",
          "text": "5.5.10. готовит предложения для включения в план работ БВА;",
          "index": 194,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        },
        {
          "id": "case11-before-5.5.13",
          "number": "5.5.13",
          "section": "5. Права и обязанности",
          "text": "5.5.13. взаимодействует c Руководителями Общества, подразделениями Общества, ДЗО по всему кругу вопросов, касающихся выполнения функций непрерывного аудита;",
          "index": 197,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        }
      ]
    }
  ],
  "after_documents": [
    {
      "id": "case11-after",
      "name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
      "version": "after",
      "kind": "polozhenie",
      "clauses": [
        {
          "id": "case11-after-1.4",
          "number": "1.4",
          "section": "1. Общие положения",
          "text": "1.4. Руководство БВА осуществляет Главный аудитор в соответствии с Уставом Общества.",
          "index": 12,
          "section_path": [
            "1.",
            "1. Общие положения"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-after-3.4",
          "number": "3.4",
          "section": "3. Структура и организация работы внутреннего аудита",
          "text": "3.4. БВА состоит из следующих структурных подразделений:\nа. Департамент ИТ-аудита и анализа данных (ДИТААД).\nб. Департамент операционного аудита (ДОА).\nв. Департамент непрерывного мониторинга системы внутреннего контроля (ДНМ).\nг. Департамент контроля качества аудита и методологии (ДККМ).",
          "index": 102,
          "section_path": [
            "3.",
            "3. Структура и организация работы внутреннего аудита"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-after-3.9",
          "number": "3.9",
          "section": "3. Структура и организация работы внутреннего аудита",
          "text": "3.9. Директору ДККМ подчиняются работники ДККМ в соответствии со штатным расписанием в составе следующих должностей:\nа. Директор проектов.\nб. Руководитель направления.",
          "index": 126,
          "section_path": [
            "3.",
            "3. Структура и организация работы внутреннего аудита"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-after-4.4",
          "number": "4.4",
          "section": "4. Внутренний аудит в ДЗО При взаимодействии с дочерними и зависимыми обществами в части организации внутреннего аудита, включая заключение договора возмездного оказания услуг на выполнение функции внутреннего аудита в ДЗО, Главный аудитор или уполномоченное им лицо осуществляет функциональное руководство и координацию деятельности подразделения ДЗО, осуществляющего функции внутреннего аудита, в соответствии с нормативными документами Общества, в том числе по следующим вопросам:",
          "text": "4.4. Организация выполнения целей и задач внутреннего аудита ДЗО на основании заключенного договора, осуществление общего руководства и распределение обязанностей между работниками БВА по целям и задачам внутреннего аудита ДЗО на основании заключенного договора. Главный аудитор может участвовать в органах управления подконтрольных Обществ, предусмотрев внедрение надлежащих мер для сохранения независимости и объективности, раскрытие информации об участии в отчетах БВА на КАУ/СД, формирование заявления о КИ. При осуществлении функции внутреннего аудита в подконтрольных обществах, имеющих статус публичного общества, силами внутреннего аудита АО «Компания», а также назначения на должность руководителя внутреннего аудита в подконтрольные общества сотрудников ВА с целью исключения потенциального конфликта интересов, БВА:\nа. информирует о потенциальном конфликте при совмещении в отчетах и плане БВА;\nб. указывает информацию о совмещении в декларациях/заявления по исключению КИ.",
          "index": 133,
          "section_path": [
            "4.",
            "4. Внутренний аудит в ДЗО При взаимодействии с дочерними и зависимыми обществами в части организации внутреннего аудита, включая заключение договора возмездного оказания услуг на выполнение функции внутреннего аудита в ДЗО, Главный аудитор или уполномоченное им лицо осуществляет функциональное руководство и координацию деятельности подразделения ДЗО, осуществляющего функции внутреннего аудита, в соответствии с нормативными документами Общества, в том числе по следующим вопросам:"
          ],
          "lead_in": null,
          "modality": "duty"
        },
        {
          "id": "case11-after-5.3",
          "number": "5.3",
          "section": "5. Права и обязанности",
          "text": "5.3. Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "index": 158,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-after-5.3.1",
          "number": "5.3.1",
          "section": "5. Права и обязанности",
          "text": "5.3.1. обеспечивают стратегическое управление аудитом по направлениям в зоне ответственности в соответствии с п. 3 настоящего Положения и планом работ БВА;",
          "index": 159,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.3.3",
          "number": "5.3.3",
          "section": "5. Права и обязанности",
          "text": "5.3.3. готовят предложения для включения в план работ БВА, взаимодействуют с субъектами СВК Общества в части:\nа. использования в своей деятельности результатов работы других субъектов СВК и иных заинтересованных сторон, включая оценку качества и надежности результатов работ субъектов СВК (в т.ч. применяемую методологию, процедуры и техники, используемые при оценке, объем и характер работ);\nб. выявления рисков с недостаточным или дублирующим покрытием субъектами СВК и иными заинтересованными сторонами в рамках Карты гарантий;",
          "index": 163,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.3.5",
          "number": "5.3.5",
          "section": "5. Права и обязанности",
          "text": "5.3.5. проводят проверки и обеспечивают выполнение плана работ БВА в том числе:\nа. контроль выполнения целей аудита, оценка соответствия результатов проверок задачам, установленным планом работ БВА;\nб. контроль качества работы проектной команды;\nв. согласование результатов проверок с Руководителями Общества по проверяемым направлениям;",
          "index": 172,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.3.7",
          "number": "5.3.7",
          "section": "5. Права и обязанности",
          "text": "5.3.7. организуют контроль устранения недостатков и нарушений, выявленных в ходе проведения проверок БВА, обеспечивают и совершенствуют работу системы мониторинга действий (корректирующих мер) Руководителей Общества, предпринимаемых по результатам внутренних аудитов и проектов.",
          "index": 177,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.3.8",
          "number": "5.3.8",
          "section": "5. Права и обязанности",
          "text": "5.3.8. анализируют результаты проверок БВА и непрерывного аудита, готовят материалы и предложения в зоне ответственности для представления Главному аудитору;",
          "index": 178,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.3.12",
          "number": "5.3.12",
          "section": "5. Права и обязанности",
          "text": "5.3.12. участвуют в разработке ВНД БВА;",
          "index": 182,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.4",
          "number": "5.4",
          "section": "5. Права и обязанности",
          "text": "5.4. Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "index": 184,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-after-5.4.2",
          "number": "5.4.2",
          "section": "5. Права и обязанности",
          "text": "5.4.2. готовит предложения для включения в план работ БВА;",
          "index": 186,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.4.5",
          "number": "5.4.5",
          "section": "5. Права и обязанности",
          "text": "5.4.5. анализирует результаты непрерывного аудита и готовит материалы и предложения в зоне ответственности для представления Главному аудитору;",
          "index": 189,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента непрерывного мониторинга системы внутреннего контроля:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.5",
          "number": "5.5",
          "section": "5. Права и обязанности",
          "text": "5.5. Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
          "index": 195,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-after-5.5.2",
          "number": "5.5.2",
          "section": "5. Права и обязанности",
          "text": "5.5.2. организует непрерывный мониторинг качества деятельности внутреннего аудита; организует периодические внутренние и внешние оценки качества всего спектра деятельности внутреннего аудита (Программа обеспечения и повышения качества внутреннего аудита);",
          "index": 197,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.5.3",
          "number": "5.5.3",
          "section": "5. Права и обязанности",
          "text": "5.5.3. готовит отчеты об итогах выполнения плана работы БВА в соответствии с требованиями настоящего Положения;",
          "index": 198,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.5.4",
          "number": "5.5.4",
          "section": "5. Права и обязанности",
          "text": "5.5.4. разрабатывает методические материалы, актуализирует ВНД, регламентирующие деятельность внутреннего аудита (единая методология внутреннего аудита);",
          "index": 199,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.5.6",
          "number": "5.5.6",
          "section": "5. Права и обязанности",
          "text": "5.5.6. организует обучение работников БВА, консультирует по сложным вопросам аудита и подготовки отчетности;",
          "index": 201,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.5.7",
          "number": "5.5.7",
          "section": "5. Права и обязанности",
          "text": "5.5.7. консолидирует полученные предложения по плану, формирует план работ БВА и представляет на рассмотрение Главному аудитору;",
          "index": 202,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.5.9",
          "number": "5.5.9",
          "section": "5. Права и обязанности",
          "text": "5.5.9. взаимодействует c Руководителями Общества, подразделениями Общества, ДЗО по всему кругу вопросов, касающихся выполнения функций внутреннего аудита;",
          "index": 204,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Директор департамента контроля качества аудита и методологии:",
          "modality": "duty"
        },
        {
          "id": "case11-after-5.8",
          "number": "5.8",
          "section": "5. Права и обязанности",
          "text": "5.8. Главный аудитор и работники БВА не имеют права:",
          "index": 227,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": null,
          "modality": "neutral"
        },
        {
          "id": "case11-after-5.8.1",
          "number": "5.8.1",
          "section": "5. Права и обязанности",
          "text": "5.8.1. выполнять функциональные обязанности, не связанные с деятельностью внутреннего аудита, как это определено в настоящем Положении, в том числе:\nа. разрабатывать дизайн хозяйственных и финансовых процессов либо участвовать в реализации таких процессов;\nб. внедрять операционные и контрольные процедуры;\nв. принимать управленческие решения;\nг. инициировать или согласовывать какие-либо бухгалтерские операции;\nд. инициировать и утверждать транзакции, не относящиеся непосредственно к деятельности БВА.",
          "index": 228,
          "section_path": [
            "5.",
            "5. Права и обязанности"
          ],
          "lead_in": "Главный аудитор и работники БВА не имеют права:",
          "modality": "prohibition"
        }
      ]
    }
  ],
  "constraints": [
    {
      "id": "constraint-bva-operational-work",
      "unit_id": null,
      "text": "Главный аудитор и работники БВА не имеют права выполнять функциональные обязанности, не связанные с деятельностью внутреннего аудита.",
      "executor": "Главный аудитор и работники БВА",
      "modality": "prohibition",
      "sources": [
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_id": "case11-after-5.8",
          "clause_number": "5.8",
          "quote": "5.8. Главный аудитор и работники БВА не имеют права:"
        },
        {
          "doc_id": "case11-after",
          "doc_name": "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx",
          "version": "after",
          "clause_id": "case11-after-5.8.1",
          "clause_number": "5.8.1",
          "quote": "5.8.1. выполнять функциональные обязанности, не связанные с деятельностью внутреннего аудита, как это определено в настоящем Положении, в том числе:"
        }
      ]
    }
  ],
  "recommendations": [
    "Проверить распределение контроля устранения недостатков между бывшим директором направления и директорами ДИТААД/ДОА (пп. 5.3.6 ред. 8; 5.3.7 ред. 9).",
    "Проверить фактические зоны ответственности ДНМ, ДИТААД и ДККМ и наличие одинаковых действий над одним объектом (пп. 5.3.8, 5.4.5, 5.5.4 ред. 9).",
    "Проверить, кто оценивает результаты работы аудиторской команды, с учётом отдельной оценки качества ДККМ (пп. 5.3.5, 5.5.2 ред. 9)."
  ]
};

export default demoReport;
