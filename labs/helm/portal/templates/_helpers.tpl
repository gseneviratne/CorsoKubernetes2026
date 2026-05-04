{{/*
Nome breve del chart, usato come componente del fullname.
*/}}
{{- define "portal.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fullname: nome univoco usato per metadata.name di tutte le risorse.
- Se l'utente fornisce fullnameOverride, ha priorita.
- Se il release name contiene gia il nome del chart, lo usa cosi.
- Altrimenti concatena release name e nome chart.
*/}}
{{- define "portal.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Nome del chart con versione, per la label helm.sh/chart.
*/}}
{{- define "portal.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Label comuni applicate a tutte le risorse generate dal chart.
*/}}
{{- define "portal.labels" -}}
helm.sh/chart: {{ include "portal.chart" . }}
{{ include "portal.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels: quelle che servono per matchLabels e per i selettori dei Service.
NON modificarle dopo il primo install: cambierebbero il selector del Deployment.
*/}}
{{- define "portal.selectorLabels" -}}
app.kubernetes.io/name: {{ include "portal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Nome del ServiceAccount da usare nel Deployment.
*/}}
{{- define "portal.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "portal.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
