import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

import 'supabase_service.dart';

class LegalRulesRetrievalService {
  LegalRulesRetrievalService({
    String? apiKey,
    SupabaseClient? client,
    http.Client? httpClient,
  })  : apiKey = apiKey ??
            const String.fromEnvironment('GEMINI_API_KEY', defaultValue: ''),
        _client = client ?? _resolveSupabaseClient(),
        _httpClient = httpClient ?? http.Client();

  static SupabaseClient? _resolveSupabaseClient() {
    if (!SupabaseService.isReady) return null;
    try {
      return Supabase.instance.client;
    } catch (_) {
      return null;
    }
  }

  static const model = 'gemini-embedding-001';
  static const vectorDimension = 3072;

  final String apiKey;
  final SupabaseClient? _client;
  final http.Client _httpClient;

  void dispose() {
    _httpClient.close();
  }

  Future<LegalRulesContext> retrieveLegalContext(String ocrText) async {
    final client = _client;
    if (client == null) {
      debugPrint('RAG: SupabaseClient not configured or offline. Returning empty legal context.');
      return const LegalRulesContext.empty();
    }
    try {
      final query = _buildQuery(ocrText);
      final embedding = await _generateEmbedding(query);
      if (embedding.isEmpty) {
        return const LegalRulesContext.empty();
      }

      final response = await client.rpc(
        'match_legal_rules',
        params: {
          'query_embedding': embedding,
          'match_threshold': 0.6,
          'match_count': 5,
        },
      );

      final rules = (response as List<dynamic>? ?? [])
          .map((item) => LegalRuleItem.fromRpcMap(item as Map<String, dynamic>))
          .toList();

      return LegalRulesContext(rules: rules);
    } catch (e) {
      debugPrint('RAG retrieval failed: $e');
      return const LegalRulesContext.empty();
    }
  }

  String _buildQuery(String ocrText) {
    final trimmed = ocrText.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (trimmed.length > 500) {
      return trimmed.substring(0, 500);
    }
    return trimmed;
  }

  Future<List<double>> _generateEmbedding(String text) async {
    if (apiKey.isEmpty) {
      debugPrint('RAG: GEMINI_API_KEY missing, skipping embeddings.');
      return const [];
    }

    final url = Uri.parse(
      'https://generativelanguage.googleapis.com/v1beta/models/$model:embedContent?key=$apiKey',
    );

    final payload = {
      'model': 'models/$model',
      'content': {
        'parts': [
          {'text': text}
        ]
      },
    };

    try {
      final response = await _httpClient.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      );

      if (response.statusCode >= 200 && response.statusCode < 300) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        final values =
            (decoded['embedding']?['values'] as List<dynamic>? ?? [])
                .map((v) => (v as num).toDouble())
                .toList();
        if (values.length == vectorDimension) {
          return values;
        }
      }
    } catch (e) {
      debugPrint('Embedding generation failed: $e');
    }

    return const [];
  }
}

class LegalRulesContext {
  const LegalRulesContext({this.rules = const []});

  const LegalRulesContext.empty() : rules = const [];

  final List<LegalRuleItem> rules;

  bool get isEmpty => rules.isEmpty;

  String get formatted => toPromptContext();

  String toPromptContext() {
    if (rules.isEmpty) return 'No matched legal rules available.';
    return rules
        .map(
          (rule) =>
              'Rule ID: ${rule.id}\n'
              'Source: ${rule.source}\n'
              'Rule: ${rule.ruleTitle}\n'
              'Category: ${rule.category}\n'
              'Summary: ${rule.ruleSummary}\n'
              'Exact Text: ${rule.exactText}\n'
              'Similarity: ${rule.similarity.toStringAsFixed(3)}',
        )
        .join('\n\n');
  }
}

class LegalRuleItem {
  const LegalRuleItem({
    required this.id,
    required this.source,
    required this.ruleTitle,
    required this.category,
    required this.ruleSummary,
    required this.exactText,
    required this.similarity,
  });

  factory LegalRuleItem.fromRpcMap(Map<String, dynamic> map) {
    return LegalRuleItem(
      id: map['id']?.toString() ?? '',
      source: map['source'] as String? ?? 'PCR, 2011',
      ruleTitle: map['rule_title'] as String? ?? 'General Declaration Rule',
      category: map['category'] as String? ?? 'General',
      ruleSummary: map['rule_summary'] as String? ?? '',
      exactText: map['exact_text'] as String? ?? '',
      similarity: (map['similarity'] as num?)?.toDouble() ?? 0.0,
    );
  }

  final String id;
  final String source;
  final String ruleTitle;
  final String category;
  final String ruleSummary;
  final String exactText;
  final double similarity;
}
