"use client";

import { useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface UploadBoxProps {
  label: string;
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
}

const MAX_FILES = 10;
const MAX_FILE_SIZE = 10 * 1024 * 1024;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} КБ`;
  return `${(bytes / (1024 * 1024)).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} МБ`;
}

export function UploadBox({ label, files, onChange, disabled = false }: UploadBoxProps) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [errors, setErrors] = useState<string[]>([]);

  function addFiles(incoming: File[]) {
    if (disabled) return;

    const nextFiles = [...files];
    const nextErrors: string[] = [];
    for (const file of incoming) {
      if (!file.name.toLowerCase().endsWith(".docx")) {
        nextErrors.push(`«${file.name}»: поддерживаются только файлы .docx.`);
      } else if (file.size > MAX_FILE_SIZE) {
        nextErrors.push(`«${file.name}»: размер превышает 10 МБ.`);
      } else if (nextFiles.length >= MAX_FILES) {
        nextErrors.push(`«${file.name}»: в одном комплекте может быть не более 10 файлов.`);
      } else {
        nextFiles.push(file);
      }
    }
    setErrors(nextErrors);
    onChange(nextFiles);
  }

  return (
    <Card aria-labelledby={`${id}-label`}>
      <CardHeader>
        <CardTitle id={`${id}-label`}>{label}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div
          className={`rounded-lg border border-dashed border-border bg-muted/40 p-6 text-center ${disabled ? "opacity-60" : "hover:border-primary"}`}
          onDragOver={(event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = disabled ? "none" : "copy";
          }}
          onDrop={(event) => {
            event.preventDefault();
            addFiles(Array.from(event.dataTransfer.files));
          }}
        >
          <p className="mb-3 text-sm">Перетащите документы сюда или выберите файлы</p>
          <input
            ref={inputRef}
            id={id}
            type="file"
            multiple
            accept=".docx"
            disabled={disabled}
            className="hidden"
            aria-labelledby={`${id}-label`}
            aria-describedby={`${id}-hint${errors.length ? ` ${id}-errors` : ""}`}
            onChange={(event) => {
              addFiles(Array.from(event.currentTarget.files ?? []));
              event.currentTarget.value = "";
            }}
          />
          <Button
            variant="secondary"
            disabled={disabled}
            aria-label={`Выбрать файлы: ${label}`}
            aria-describedby={`${id}-hint`}
            onClick={() => inputRef.current?.click()}
          >
            Выбрать файлы
          </Button>
          <p id={`${id}-hint`} className="mt-3 text-xs text-muted-foreground">
            Только .docx · до 10 файлов · до 10 МБ каждый
          </p>
        </div>

        {errors.length > 0 ? (
          <ul id={`${id}-errors`} role="alert" className="space-y-1 break-words text-sm text-danger">
            {errors.map((error, index) => <li key={index}>{error}</li>)}
          </ul>
        ) : null}

        <p className="text-sm text-muted-foreground" role="status">
          {files.length ? `Выбрано файлов: ${files.length} из ${MAX_FILES}` : "Файлы пока не выбраны"}
        </p>
        {files.length > 0 ? (
          <ul className="divide-y divide-border">
            {files.map((file, index) => (
              <li key={`${file.name}-${index}`} className="flex items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="break-words text-sm font-medium">{file.name}</p>
                  <p className="text-xs text-muted-foreground">{formatSize(file.size)}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={disabled}
                  aria-label={`Убрать ${file.name}`}
                  onClick={() => {
                    onChange(files.filter((_, fileIndex) => fileIndex !== index));
                    setErrors([]);
                  }}
                >
                  Убрать
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
