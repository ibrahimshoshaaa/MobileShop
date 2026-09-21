import 'dart:convert';
import 'dart:io';

/// Thrown when the server returns an error or is unreachable.
class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

/// HTTP client for the Mobile Shop ERP backend API.
/// Mirrors apps/desktop/api_client.py — same endpoints, same auth header,
/// same error shape ({ ok: bool, error: { message } }).
class ApiClient {
  ApiClient({
    required this.baseUrl,
    required this.token,
    required this.branchId,
  });

  final String baseUrl;
  final String token;
  final String branchId;

  static const _timeout = Duration(seconds: 15);

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final uri = Uri.parse('${baseUrl.replaceFirst(RegExp(r'/+
    final client = HttpClient();
    try {
      final request = await (switch (method) {
        'GET' => client.getUrl(uri),
        'POST' => client.postUrl(uri),
        _ => throw StateError('Unsupported method: $method'),
      })
          .timeout(_timeout);

      request.headers.set('Authorization', 'Bearer $token');
      request.headers.set('Content-Type', 'application/json');

      if (body != null) {
        final encoded = utf8.encode(jsonEncode(body));
        request.contentLength = encoded.length;
        request.add(encoded);
      }

      final response = await request.close().timeout(_timeout);
      final responseBody = await response.transform(utf8.decoder).join();
      final json = jsonDecode(responseBody) as Map<String, dynamic>;

      if (response.statusCode >= 400) {
        final msg = ((json['error'] as Map<String, dynamic>?)?['message'] as String?) ??
            'خطأ من السيرفر (كود ${response.statusCode}).';
        throw ApiException(msg);
      }
      if (json['ok'] == false) {
        final msg = ((json['error'] as Map<String, dynamic>?)?['message'] as String?) ??
            'فشلت العملية.';
        throw ApiException(msg);
      }
      return json;
    } on SocketException catch (e) {
      throw ApiException('تعذّر الاتصال بالسيرفر على $baseUrl: ${e.message}');
    } on HttpException catch (e) {
      throw ApiException('خطأ HTTP: ${e.message}');
    } finally {
      client.close();
    }
  }

  /// Send a command (write operation) to POST /command.
  Future<Map<String, dynamic>> command(
    String commandId,
    String commandName,
    Map<String, dynamic> payload,
  ) async {
    final result = await _request('POST', '/command', body: {
      'commandId': commandId,
      'command': commandName,
      'branchId': branchId,
      'payload': payload,
    });
    return (result['data'] as Map<String, dynamic>?) ?? {};
  }

  /// Read a list resource from GET /query/<entity>.
  Future<List<Map<String, dynamic>>> query(String entity, {int limit = 100}) async {
    final result = await _request(
      'GET',
      '/query/$entity?branch_id=$branchId&limit=$limit',
    );
    return List<Map<String, dynamic>>.from(result['data'] as List? ?? []);
  }

  /// GET /sales
  Future<List<Map<String, dynamic>>> getSales({int limit = 50}) async {
    final result = await _request(
      'GET',
      '/sales?branch_id=$branchId&limit=$limit',
    );
    return List<Map<String, dynamic>>.from(result['data'] as List? ?? []);
  }

  /// Convenience: new UUID-style command ID.
  static String newCommandId([String prefix = 'cmd']) {
    final ts = DateTime.now().millisecondsSinceEpoch;
    return '$prefix-$ts-${_rand()}';
  }

  static int _rand() => (DateTime.now().microsecond * 1000 + DateTime.now().millisecond) & 0xFFFF;
}
), '')}$path');
    final client = HttpClient();
    try {
      final request = await (switch (method) {
        'GET' => client.getUrl(uri),
        'POST' => client.postUrl(uri),
        _ => throw StateError('Unsupported method: $method'),
      })
          .timeout(_timeout);

      request.headers.set('Authorization', 'Bearer $token');
      request.headers.set('Content-Type', 'application/json');

      if (body != null) {
        final encoded = utf8.encode(jsonEncode(body));
        request.contentLength = encoded.length;
        request.add(encoded);
      }

      final response = await request.close().timeout(_timeout);
      final responseBody = await response.transform(utf8.decoder).join();
      final json = jsonDecode(responseBody) as Map<String, dynamic>;

      if (response.statusCode >= 400) {
        final msg = ((json['error'] as Map<String, dynamic>?)?['message'] as String?) ??
            'خطأ من السيرفر (كود ${response.statusCode}).';
        throw ApiException(msg);
      }
      if (json['ok'] == false) {
        final msg = ((json['error'] as Map<String, dynamic>?)?['message'] as String?) ??
            'فشلت العملية.';
        throw ApiException(msg);
      }
      return json;
    } on SocketException catch (e) {
      throw ApiException('تعذّر الاتصال بالسيرفر على $baseUrl: ${e.message}');
    } on HttpException catch (e) {
      throw ApiException('خطأ HTTP: ${e.message}');
    } finally {
      client.close();
    }
  }

  /// Send a command (write operation) to POST /command.
  Future<Map<String, dynamic>> command(
    String commandId,
    String commandName,
    Map<String, dynamic> payload,
  ) async {
    final result = await _request('POST', '/command', body: {
      'commandId': commandId,
      'command': commandName,
      'branchId': branchId,
      'payload': payload,
    });
    return (result['data'] as Map<String, dynamic>?) ?? {};
  }

  /// Read a list resource from GET /query/<entity>.
  Future<List<Map<String, dynamic>>> query(String entity, {int limit = 100}) async {
    final result = await _request(
      'GET',
      '/query/$entity?branch_id=$branchId&limit=$limit',
    );
    return List<Map<String, dynamic>>.from(result['data'] as List? ?? []);
  }

  /// GET /sales
  Future<List<Map<String, dynamic>>> getSales({int limit = 50}) async {
    final result = await _request(
      'GET',
      '/sales?branch_id=$branchId&limit=$limit',
    );
    return List<Map<String, dynamic>>.from(result['data'] as List? ?? []);
  }

  /// Convenience: new UUID-style command ID.
  static String newCommandId([String prefix = 'cmd']) {
    final ts = DateTime.now().millisecondsSinceEpoch;
    return '$prefix-$ts-${_rand()}';
  }

  static int _rand() => (DateTime.now().microsecond * 1000 + DateTime.now().millisecond) & 0xFFFF;
}
