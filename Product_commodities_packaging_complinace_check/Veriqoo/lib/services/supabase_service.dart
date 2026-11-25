import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'compliance_analysis.dart';

class SupabaseService {
  static bool isReady = false;

  SupabaseService({SupabaseClient? client})
    : _client = client ?? _resolveClient();

  static SupabaseClient? _resolveClient() {
    if (!isReady) return null;
    try {
      return Supabase.instance.client;
    } catch (_) {
      return null;
    }
  }

  final SupabaseClient? _client;

  bool get isConfigured => _client != null;

  Future<void> testConnection() async {
    if (_client == null) return;
    try {
      await _client.from('supabase_test').insert({
        'message': 'Supabase connection test',
        'created_at': DateTime.now().toUtc().toIso8601String(),
      });
    } catch (e) {
      debugPrint('Supabase connection test error: $e');
    }
  }

  Future<void> saveInspectionReport({
    required ComplianceAnalysis analysis,
    required String ocrText,
    XFile? primaryImage,
    String? imageUrl,
    DateTime? inspectedAt,
  }) async {
    if (_client == null) {
      debugPrint('Supabase is not configured or in offline mode. Inspection saved locally only.');
      return;
    }
    try {
      final accessibleImageUrl =
          imageUrl ??
          (primaryImage == null
              ? null
              : await uploadPackagedProductImage(primaryImage));

      final status = analysis.isCompliant ? 'compliant' : 'non-compliant';
      final score = analysis.isCompliant
          ? 100
          : (100 - (analysis.possibleIssues.length * 15 + analysis.missingInformation.length * 10))
              .clamp(0, 100);
      final summary = analysis.isCompliant
          ? 'Compliant product packaged commodity'
          : 'Found ${analysis.possibleIssues.length} issues and ${analysis.missingInformation.length} missing declarations';

      final payload = {
        'product_name': analysis.productName,
        'compliance_status': status,
        'compliance_score': score,
        'summary': summary,
        'ocr_text': ocrText,
        'image_url': accessibleImageUrl,
        'issues_found': analysis.possibleIssues
            .map(
              (issue) => {
                'field': issue.title,
                'status': issue.severity,
                'issue': issue.description,
                'recommendation': issue.legalBasis ?? '',
                'legal_rule_ids': issue.ruleNumbers,
                'verification_status': issue.verificationStatus.value,
                'legal_basis': issue.legalBasis,
                'ocr_evidence': issue.ocrEvidence,
              },
            )
            .toList(),
        'inspected_at': (inspectedAt ?? DateTime.now().toUtc())
            .toIso8601String(),
      };

      await _client.from('inspections').insert(payload);
    } catch (e) {
      debugPrint('Failed to save inspection report to Supabase: $e');
    }
  }

  Future<String?> uploadPackagedProductImage(XFile image) async {
    if (_client == null) return null;
    try {
      final bytes = await image.readAsBytes();
      final extension = image.name.split('.').last;
      final path =
          'inspections/${DateTime.now().millisecondsSinceEpoch}_${image.name}';

      await _client.storage.from('packaged_products').uploadBinary(
            path,
            bytes,
            fileOptions: FileOptions(
              contentType: 'image/$extension',
              upsert: true,
            ),
          );

      return _client.storage.from('packaged_products').getPublicUrl(path);
    } catch (e) {
      debugPrint('Error uploading image to Supabase Storage: $e');
      return null;
    }
  }
}
