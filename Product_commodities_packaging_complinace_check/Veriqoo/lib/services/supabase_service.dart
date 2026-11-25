import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'compliance_analysis.dart';

class SupabaseService {
  SupabaseService({SupabaseClient? client})
    : _client = client ?? (Supabase.instance.isInitialized ? Supabase.instance.client : null);

  final SupabaseClient? _client;

  bool get isConfigured => _client != null;

  Future<void> testConnection() async {
    if (_client == null) return;
    await _client.from('supabase_test').insert({
      'message': 'Supabase connection test',
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
  }

  Future<void> saveInspectionReport({
    required ComplianceAnalysis analysis,
    required String ocrText,
    XFile? primaryImage,
    String? imageUrl,
    DateTime? inspectedAt,
  }) async {
    if (_client == null) {
      throw StateError('Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY to enable remote persistence.');
    }
    final accessibleImageUrl =
        imageUrl ??
        (primaryImage == null
            ? null
            : await uploadInspectionImage(primaryImage));

    await _client.from('inspections').insert({
      'product_name': analysis.productName,
      'mrp': analysis.mrp,
      'net_quantity': analysis.netQuantity,
      'manufacturer': analysis.manufacturer,
      'address': analysis.address,
      'packing_date': analysis.packingDate,
      'customer_care': analysis.customerCare,
      'missing_information': analysis.missingInformation,
      'possible_issues': analysis.possibleIssues
          .map((issue) => issue.toJson())
          .toList(),
      'is_compliant': analysis.isCompliant,
      'ocr_text': ocrText,
      'ai_report': analysis.toJson(),
      'inspected_at': (inspectedAt ?? DateTime.now()).toUtc().toIso8601String(),
      'image_url': accessibleImageUrl,
    });
  }

  Future<String> uploadInspectionImage(XFile image) async {
    if (_client == null) {
      throw StateError('Supabase storage not configured.');
    }
    const bucketName = 'inspection-images';
    final bytes = await image.readAsBytes();
    final extension = _fileExtension(image.name);
    final path = '${DateTime.now().toUtc().microsecondsSinceEpoch}.$extension';

    await _client.storage
        .from(bucketName)
        .uploadBinary(
          path,
          bytes,
          fileOptions: FileOptions(contentType: _mimeType(extension)),
        );

    return _client.storage.from(bucketName).getPublicUrl(path);
  }

  String _fileExtension(String filename) {
    final parts = filename.split('.');
    return parts.length > 1 ? parts.last.toLowerCase() : 'jpg';
  }

  String _mimeType(String extension) {
    switch (extension) {
      case 'png':
        return 'image/png';
      case 'webp':
        return 'image/webp';
      case 'jpeg':
      case 'jpg':
      default:
        return 'image/jpeg';
    }
  }
}
