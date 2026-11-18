{{/* Names */}}
{{- define "puppetboard.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "puppetboard.fullname" -}}
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

{{- define "puppetboard.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Labels */}}
{{- define "puppetboard.selectorLabels" -}}
app.kubernetes.io/name: {{ include "puppetboard.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "puppetboard.labels" -}}
helm.sh/chart: {{ include "puppetboard.chart" . }}
{{ include "puppetboard.selectorLabels" . }}
app.kubernetes.io/version: {{ include "puppetboard.imageTag" . | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{/* Metadata block. Usage: include "puppetboard.metadata" (dict "context" $ "name" "x" "annotations" ..) */}}
{{- define "puppetboard.metadata" -}}
metadata:
  name: {{ .name }}
  namespace: {{ .context.Release.Namespace }}
  labels:
    {{- include "puppetboard.labels" .context | nindent 4 }}
  {{- $all := mergeOverwrite (dict) (default (dict) .context.Values.commonAnnotations) (default (dict) .annotations) }}
  {{- with $all }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end -}}

{{/* Image */}}
{{- define "puppetboard.imageTag" -}}
{{- default .Chart.AppVersion .Values.image.tag | toString | trunc 63 | replace "+" "_" -}}
{{- end -}}

{{- define "puppetboard.image" -}}
{{- $repo := .Values.image.repository -}}
{{- if .Values.image.registry -}}{{- $repo = printf "%s/%s" .Values.image.registry $repo -}}{{- end -}}
{{- if .Values.image.digest -}}
{{- printf "%s@%s" $repo .Values.image.digest -}}
{{- else -}}
{{- printf "%s:%s" $repo (include "puppetboard.imageTag" .) -}}
{{- end -}}
{{- end -}}

{{- define "puppetboard.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "puppetboard.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/* Secret names */}}
{{- define "puppetboard.secretName" -}}
{{- default (include "puppetboard.fullname" .) .Values.existingSecret -}}
{{- end -}}

{{- define "puppetboard.tlsSecretName" -}}
{{- default (printf "%s-puppetdb-tls" (include "puppetboard.fullname" . | trunc 49 | trimSuffix "-")) .Values.puppetdb.tls.existingSecret -}}
{{- end -}}

{{/* Host names MCP accepts: mcp.allowedHosts, else the ingress and httpRoute hosts. */}}
{{- define "puppetboard.mcpAllowedHosts" -}}
{{- $hosts := .Values.mcp.allowedHosts -}}
{{- if not $hosts -}}
{{- $hosts = list -}}
{{- if .Values.ingress.enabled -}}
{{- range .Values.ingress.hosts }}{{- $hosts = append $hosts .host -}}{{- end -}}
{{- end -}}
{{- if .Values.httpRoute.enabled -}}
{{- range .Values.httpRoute.hostnames }}{{- $hosts = append $hosts . -}}{{- end -}}
{{- end -}}
{{- end -}}
{{- join "," (uniq $hosts) -}}
{{- end -}}

{{/* Checks that stop a broken installation early. */}}
{{- define "puppetboard.validate" -}}
{{- if and (not .Values.secretKey) (not .Values.existingSecret) -}}
{{- fail "puppetboard: set secretKey (openssl rand -hex 32) or existingSecret" -}}
{{- end -}}
{{- if and .Values.puppetdb.tls.enabled (not .Values.puppetdb.tls.existingSecret) (not (and .Values.puppetdb.tls.ca .Values.puppetdb.tls.cert .Values.puppetdb.tls.key)) -}}
{{- fail "puppetboard: puppetdb.tls needs existingSecret or ca, cert and key" -}}
{{- end -}}
{{- if and .Values.mcp.enabled (not (include "puppetboard.mcpAllowedHosts" .)) -}}
{{- fail "puppetboard: mcp.enabled needs mcp.allowedHosts or an ingress/httpRoute host" -}}
{{- end -}}
{{- end -}}
